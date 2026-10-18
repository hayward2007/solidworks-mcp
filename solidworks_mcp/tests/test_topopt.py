"""Topology optimisation tests:  python -m unittest solidworks_mcp.tests.test_topopt"""
import unittest
from collections import Counter

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from solidworks_mcp.topopt import elements, export
from solidworks_mcp.topopt.problem import from_spec, parse_tpd, to_tpd
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
