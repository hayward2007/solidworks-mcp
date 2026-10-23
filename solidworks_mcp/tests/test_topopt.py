"""Topology optimisation tests:  python -m unittest solidworks_mcp.tests.test_topopt"""
import unittest
from collections import Counter

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from solidworks_mcp.topopt import elements, export, physics
from solidworks_mcp.topopt.problem import from_spec, parse_tpd, to_tpd
from solidworks_mcp.topopt.run import auto_volume, optimise
from solidworks_mcp.topopt.topology import Topology

MBB = """[ToPy Problem Definition File v2007]
PROB_TYPE  : comp
PROB_NAME  : beam_2d_reci
ETA        : 0.5
DOF_PN     : 2
VOL_FRAC   : 0.5
FILT_RAD   : 1.5
ELEM_K     : Q4
NUM_ELEM_X : 60
NUM_ELEM_Y : 20
NUM_ELEM_Z : 0
FXTR_NODE_X: 1|21
FXTR_NODE_Y: 1281
LOAD_NODE_Y: 1
LOAD_VALU_Y: -1
NUM_ITER   : 94
P_FAC      : 3
"""


def lk99(nu=0.3):
    """Element stiffness of Sigmund's 99-line code."""
    k = np.array([1/2 - nu/6, 1/8 + nu/8, -1/4 - nu/12, -1/8 + 3*nu/8, -1/4 + nu/12, -1/8 - nu/8, nu/6, 1/8 - 3*nu/8])
    i = [[0, 1, 2, 3, 4, 5, 6, 7], [1, 0, 7, 6, 5, 4, 3, 2], [2, 7, 0, 5, 6, 3, 4, 1], [3, 6, 5, 0, 7, 2, 1, 4],
         [4, 5, 6, 7, 0, 1, 2, 3], [5, 4, 3, 2, 1, 0, 7, 6], [6, 3, 4, 1, 2, 7, 0, 5], [7, 2, 1, 4, 3, 6, 5, 0]]
    return 1 / (1 - nu ** 2) * k[np.array(i)]


class Elements(unittest.TestCase):
    def test_q4_is_the_99_line_element(self):
        np.testing.assert_allclose(elements.q4(1.0, 0.3), lk99(0.3), atol=1e-14)

    def test_rigid_body_modes(self):
        for name, n0 in (("Q4", 3), ("Q5B", 3), ("Q4A5B", 3), ("H8", 6), ("H18B", 6)):
            K = elements.element_matrix(name)
            np.testing.assert_allclose(K, K.T, atol=1e-14)
            self.assertEqual(int((np.linalg.eigvalsh(K) < 1e-9).sum()), n0, name)


class Optimiser(unittest.TestCase):
    def test_mbb_matches_sigmund_99_line(self):
        """First iterations of the classic MBB beam against an independent 99-line transcription."""
        prob = parse_tpd(MBB)
        prob["ELEM_K"] = elements.q4(1.0, 0.3)
        t = Topology(prob)
        port = [t.step()["objective"] for _ in range(8)]
        nelx, nely, KE = 60, 20, lk99(0.3)
        x = np.full((nely, nelx), 0.5)
        ndof = 2 * (nelx + 1) * (nely + 1)
        el = [(elx, ely) for elx in range(nelx) for ely in range(nely)]
        edof = np.array([[2 * n1, 2 * n1 + 1, 2 * n2, 2 * n2 + 1, 2 * n2 + 2, 2 * n2 + 3, 2 * n1 + 2, 2 * n1 + 3]
                         for elx, ely in el for n1, n2 in [((nely + 1) * elx + ely, (nely + 1) * (elx + 1) + ely)]])
        free = np.setdiff1d(np.arange(ndof), np.union1d(np.arange(0, 2 * (nely + 1), 2), [ndof - 1]))
        F = np.zeros(ndof)
        F[1] = -1
        H = t.H                                                       # same Sigmund weights (row-major)
        ref = []
        for _ in range(8):
            xe = np.array([x[ely, elx] for elx, ely in el])
            K = sp.coo_matrix(((xe[:, None] ** 3 * KE.ravel()[None, :]).ravel(),
                               (np.repeat(edof, 8, axis=1).ravel(), np.tile(edof, (1, 8)).ravel())), shape=(ndof, ndof)).tocsc()
            U = np.zeros(ndof)
            U[free] = spla.spsolve(K[free][:, free], F[free])
            ce = np.einsum("ij,jk,ik->i", U[edof], KE, U[edof])
            ref.append(float((xe ** 3 * ce).sum()))
            dc = np.zeros((nely, nelx))
            for n, (elx, ely) in enumerate(el):
                dc[ely, elx] = -3 * x[ely, elx] ** 2 * ce[n]
            dc = ((H @ (x.ravel() * dc.ravel())) / (np.asarray(H.sum(axis=1)).ravel() * x.ravel())).reshape(x.shape)
            l1, l2 = 0.0, 1e5
            while (l2 - l1) / (l2 + l1) > 1e-8:
                lm = 0.5 * (l1 + l2)
                xn = np.maximum(0.001, np.maximum(x - 0.2, np.minimum(1.0, np.minimum(x + 0.2, x * np.sqrt(-dc / lm)))))
                l1, l2 = (lm, l2) if xn.sum() > 0.5 * nelx * nely else (l1, lm)
            x = xn
        np.testing.assert_allclose(port, ref, rtol=1e-9)
        self.assertAlmostEqual(port[0], 1007.022108, places=5)

    def test_bracket_spec_and_contours(self):
        spec = {"size": [60, 30], "element_size": 1.0, "thickness": 5, "volume_fraction": 0.4,
                "supports": [{"edge": "left"}], "loads": [{"at": [60, 15], "force": [0, -100]}],
                "keep_out": [{"circle": [15, 15, 5]}], "iterations": 60, "material": {"E": 70000}}
        prob, meta = from_spec(spec)
        t = Topology(prob)
        t.run()
        self.assertAlmostEqual(t.desvars.mean(), 0.4, places=6)
        loops = export.contours(t.desvars, meta["h"], meta["size"])
        self.assertGreaterEqual(len(loops), 2)
        area = export.loops_area(loops)
        self.assertLess(abs(area - t.desvars.sum()) / t.desvars.sum(), 0.05)
        prob2 = parse_tpd(to_tpd(prob))
        np.testing.assert_array_equal(np.sort(prob2["FIX_DOF"]), np.sort(prob["FIX_DOF"]))

    def test_mechanism_inverter(self):
        tpd = MBB.replace("PROB_TYPE  : comp", "PROB_TYPE  : mech").replace("NUM_ELEM_X : 60", "NUM_ELEM_X : 40")
        tpd = tpd.replace("FXTR_NODE_X: 1|21\nFXTR_NODE_Y: 1281\nLOAD_NODE_Y: 1\nLOAD_VALU_Y: -1",
                          "FXTR_NODE_X: 20; 21\nFXTR_NODE_Y: 1|841|21; 20; 21\nLOAD_NODE_X: 1\nLOAD_VALU_X: 1\n"
                          "LOAD_NODE_X_OUT: 841\nLOAD_VALU_X_OUT: -1").replace("NUM_ITER   : 94", "NUM_ITER   : 40")
        t = Topology(parse_tpd(tpd))
        t.run()
        self.assertLess(t.objfval, 0.0)                               # output moves against the input


def uniform(spec):
    """Solve once on a fully solid design (no optimisation)."""
    prob, meta = from_spec(spec)
    t = Topology(prob)
    t.desvars[:] = 1.0
    t.fea()
    return t, prob, meta


def nodes_at_x(nx, ny, x):
    coords = np.c_[np.repeat(np.arange(nx + 1), ny + 1), np.tile(np.arange(ny, -1, -1), nx + 1)]
    return np.nonzero(coords[:, 0] == x)[0]


AL = {"E": 69000, "nu": 0.33, "yield": 240, "density": 2.7, "k": 167}


class Thermal(unittest.TestCase):
    """Closed-form checks of the conduction and film terms (design heat = 2 x maximum)."""
    BAR = {"size": [40, 10], "element_size": 1, "thickness": 2, "type": "thermal", "material": {"k": 150}}

    def test_conduction_bar(self):
        t, _, meta = uniform({**self.BAR, "thermal": {"sinks": [{"edge": "left"}], "sources": [{"edge": "right", "power_W": 1.0}]}})
        self.assertEqual(meta["safety_factor"], 2.0)
        expected = 2.0 * 40 / (0.150 * 10 * 2)                      # P_design L / (k W t), k in W/(mm K)
        self.assertLess(abs(t.theta[nodes_at_x(40, 10, 40)].mean() / expected - 1), 0.005)

    def test_edge_film_and_plate_film(self):
        t, _, _ = uniform({**self.BAR, "thermal": {"sources": [{"edge": "left", "power_W": 1.0}],
                                                   "convection": [{"edge": "right", "h_W_m2K": 50}]}})
        film = 2.0 / (50e-6 * 2 * 10)                                # P_design / (h t W)
        self.assertAlmostEqual(t.theta[nodes_at_x(40, 10, 40)].mean() / film, 1.0, places=6)
        self.assertLess(abs(t.theta[nodes_at_x(40, 10, 0)].mean() - film - 2.0 * 40 / (0.150 * 10 * 2)), 0.1)
        t2, _, _ = uniform({"size": [20, 20], "element_size": 1, "thickness": 2, "type": "thermal", "material": {"k": 150}, "volume_fraction": 1.0,
                            "thermal": {"sources": [{"box": [0, 0, 20, 20], "power_W": 0.5}], "plate_faces": {"h_W_m2K": 10}}})
        self.assertAlmostEqual(t2.theta.mean() / (1.0 / (2 * 10e-6 * 400)), 1.0, places=4)   # energy balance

    def test_h8_conduction(self):
        K = physics.conduction_h8()
        np.testing.assert_allclose(K, K.T, atol=1e-14)
        np.testing.assert_allclose(K.sum(axis=1), 0, atol=1e-14)
        self.assertEqual(int((np.linalg.eigvalsh(K) < 1e-12).sum()), 1)
        t, _, _ = uniform({"size": [20, 4, 4], "element_size": 1, "type": "thermal", "material": {"k": 100},
                           "thermal": {"sinks": [{"face": "x0"}], "sources": [{"face": "x1", "power_W": 0.5}]}})
        hottest = np.sort(t.theta)[-25:].mean()                       # the 5 x 5 nodes of the x1 face
        self.assertLess(abs(hottest / (1.0 * 20 / (0.1 * 16)) - 1), 0.05)   # P_design L / (k A)

    def test_thermal_needs_conductivity_sink_and_source(self):
        with self.assertRaises(ValueError): from_spec({**self.BAR, "material": {}, "thermal": {"sinks": [{"edge": "left"}], "sources": [{"edge": "right", "power_W": 1}]}})
        with self.assertRaises(ValueError): from_spec({**self.BAR, "thermal": {"sources": [{"edge": "right", "power_W": 1}]}})
        with self.assertRaises(ValueError): from_spec({**self.BAR, "thermal": {"sinks": [{"edge": "left"}]}})


class SafetyFactor(unittest.TestCase):
    PLATE = {"size": [40, 10], "element_size": 1, "thickness": 2, "material": AL,
             "supports": [{"edge": "left", "fix": "x"}, {"at": [0, 0], "fix": "xy"}], "loads": [{"edge": "right", "force": [100, 0]}]}

    def test_factor_is_at_least_two_and_scales_the_loads(self):
        prob, meta = from_spec(self.PLATE)
        self.assertAlmostEqual(float(np.sum(prob["LOAD_VAL"])), 200.0)
        self.assertAlmostEqual(from_spec({**self.PLATE, "safety_factor": 3})[0]["LOAD_VAL"].sum(), 300.0)
        with self.assertRaises(ValueError): from_spec({**self.PLATE, "safety_factor": 1.5})
        crowded = {**self.PLATE, "volume_fraction": 0.3, "keep_in": [{"box": [0, 0, 20, 10]}]}
        with self.assertRaisesRegex(ValueError, "keep-in"): from_spec(crowded)       # no freedom left to optimise

    def test_stress_recovery_in_tension(self):
        t, _, _ = uniform(self.PLATE)
        s = physics.element_stress(t.u, t.edof, 2, 0.33, 1.0, 2.0)
        self.assertAlmostEqual(float(np.median(s[:, 0])), 200 / (10 * 2), places=5)

    def test_joint_sizing_at_the_design_force(self):
        g = physics.joint_geometry({"type": "bolt", "size": 5}, 1.0)
        self.assertEqual((g["hole_mm"], g["keep_in_radius_mm"]), (5.5, 7.5))
        rows = {r["check"]: r for r in physics.joint_checks({"type": "bolt", "size": 5}, g, 600.0, 4.0, {"yield": 240}, 2.0)["rows"]}
        self.assertAlmostEqual(rows["part bearing"]["demand"], 600 / (5 * 4))
        self.assertAlmostEqual(rows["part tear-out edge distance"]["demand"], 2.75 + 600 * 3 ** 0.5 / (2 * 4 * 240), places=3)
        tapped = physics.joint_geometry({"type": "tapped", "size": 4}, 1.0)
        out = physics.joint_checks({"type": "tapped", "size": 4}, tapped, 600.0, 4.0, {"yield": 240}, 2.0)
        engagement = next(r for r in out["rows"] if r["check"] == "thread engagement")
        self.assertFalse(out["pass"])                                # M4 8.8 strips a 4 mm aluminium thread first
        self.assertAlmostEqual(engagement["demand"], 640 * 8.78 / (240 / 3 ** 0.5 * 0.75 * np.pi * 4), places=2)
        with self.assertRaises(ValueError): physics.joint_geometry({"type": "bolt", "size": 7}, 1.0)


BRACKET = {"size": [40, 24], "element_size": 1.0, "thickness": 4, "volume_fraction": 0.45, "material": AL, "iterations": 25,
           "interfaces": [{"type": "bolt", "size": 4, "at": [6, 5], "role": "support", "sink": True},
                          {"type": "bolt", "size": 4, "at": [6, 19], "role": "support", "sink": True},
                          {"type": "tapped", "size": 4, "at": [34, 12], "role": "load", "force": [0, -150], "engagement": 8},
                          {"type": "pad", "box": [18, 9, 26, 15], "role": "thermal", "heat_W": 2}],
           "thermal": {"reference_C": 40, "max_temperature_C": 85, "plate_faces": {"h_W_m2K": 8}}}


class MultiPhysics(unittest.TestCase):
    def test_interfaces_become_holes_rings_and_boundary_conditions(self):
        prob, meta = from_spec(BRACKET)
        self.assertEqual(meta["physics"], "stiffness+thermal")
        bolt = meta["interfaces"][0]
        self.assertEqual((bolt["hole_mm"], bolt["keep_in_radius_mm"]), (4.5, 6.0))
        cen = np.c_[[(i + 0.5, 24 - j - 0.5) for i in range(40) for j in range(24)]]
        d = np.hypot(cen[:, 0] - 6, cen[:, 1] - 5)
        self.assertTrue(set(np.nonzero(d <= 2.25)[0]) <= set(prob["PASV_ELEM"].tolist()))
        self.assertTrue(set(np.nonzero((d > 2.25) & (d <= 6.0))[0]) <= set(prob["ACTV_ELEM"].tolist()))
        self.assertAlmostEqual(float(prob["LOAD_VAL"].sum()), -300.0)
        self.assertAlmostEqual(float(prob["THERMAL"]["Q"].sum()), 4.0)
        self.assertGreater(len(prob["THERMAL"]["FIX"]), 0)
        pads = [dict(i) for i in BRACKET["interfaces"]]
        del pads[3]["role"]                                          # a pad without a role is a thermal pad, not a support
        self.assertEqual(from_spec({**BRACKET, "interfaces": pads})[1]["interfaces"][3]["role"], "thermal")

    def test_run_keeps_volume_normalises_and_checks(self):
        t, prob, meta, summary, check = optimise(BRACKET)
        self.assertAlmostEqual(t.desvars.mean(), 0.45, places=5)
        self.assertAlmostEqual(t.history[0]["objective"], 1.0, places=9)  # each term divided by its first value
        self.assertLess(t.history[-1]["objective"], 1.0)
        names = {c["check"] for c in check["checks"]}
        self.assertEqual(names, {"stress_vm_design_MPa", "temperature_max_design_C"})
        self.assertEqual(len(check["joints"]), 3)
        self.assertGreater(check["thermal"]["max_design_C"], check["thermal"]["max_at_max_heat_C"])
        support = [j for j in check["joints"] if j["role"] == "support"]
        self.assertAlmostEqual(sum(j["force_design_vector_N"][1] for j in support), 300.0, places=3)   # reactions balance the load

    def test_auto_volume_fraction_finds_the_lightest_passing_design(self):
        spec = {**BRACKET, "volume_fraction": "auto", "auto_range": [0.2, 0.7], "auto_steps": 3, "iterations": 15}
        (t, prob, meta, summary, check), auto = auto_volume(spec)
        self.assertTrue(auto["feasible"])
        self.assertTrue(check["field_checks_pass"])
        self.assertAlmostEqual(t.desvars.mean(), auto["chosen"], places=4)
        failing = [h["volume_fraction"] for h in auto["history"] if not h["pass"]]
        self.assertTrue(all(v < auto["chosen"] for v in failing))


class Surfaces(unittest.TestCase):
    def test_sphere_mesh_is_closed_and_manifold(self):
        n, r = 20, 7.0
        z, y, x = np.mgrid[0:n, 0:n, 0:n]
        field = (((x - 9.5) ** 2 + (y - 9.5) ** 2 + (z - 9.5) ** 2) < r ** 2).astype(float)
        V, F = export.surface(field, 1.0)
        e = Counter()
        for a, b, c in F:
            for u, v in ((a, b), (b, c), (c, a)):
                e[(min(u, v), max(u, v))] += 1
        self.assertTrue(all(k == 2 for k in e.values()))
        tri = V[F]
        vol = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() / 6
        self.assertLess(abs(vol - 4 / 3 * np.pi * r ** 3) / vol, 0.03)


if __name__ == "__main__":
    unittest.main()
