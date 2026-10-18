"""Gear geometry tests (no SolidWorks needed):  python -m unittest solidworks_mcp.tests.test_gears"""
import math
import unittest

from solidworks_mcp.gears import api, bevel, geometry as G


def _gap(loop):
    def end(s):
        return s["end"] if s["type"] == "arc" else s["points"][-1]

    def start(s):
        return s["start"] if s["type"] == "arc" else s["points"][0]
    segs = loop["segments"]
    return max(math.dist(end(a), start(b)) for a, b in zip(segs, segs[1:] + segs[:1]))


class InvoluteGears(unittest.TestCase):
    def test_inv_roundtrip(self):
        for a in (0.05, 0.3, 0.6, 1.0):
            self.assertAlmostEqual(G.inv_inverse(G.inv(a)), a, places=12)

    def test_generated_flank_is_the_involute(self):
        for m, z, x, beta in ((2, 20, 0.0, 0.0), (1, 13, 0.3, 0.0), (2, 25, 0.1, 20.0)):
            g = G.Gear(m, z, profile_shift=x, helix_angle=beta, backlash=0.1)
            _, curve = g._external_half(g.ra)
            on = [abs(math.atan2(px, py) - (math.pi / z - g.half_thickness_angle(math.hypot(px, py))))
                  * math.hypot(px, py) for px, py in curve[:-1] if math.hypot(px, py) > g.rb * 1.01]
            self.assertGreater(len(on), 20)
            self.assertLess(sorted(on)[len(on) // 2], 1e-9)          # flank points lie on the involute

    def test_tooth_spaces_are_closed_loops(self):
        for g in (G.Gear(2, 20), G.Gear(0.5, 8), G.Gear(1, 60, internal=True), G.Gear(2, 36, internal=True),
                  G.Gear(1, 30, internal=True)):
            self.assertLess(_gap(g.tooth_space()), 1e-9)

    def test_undercut_is_flagged_and_cut_out(self):
        g = G.Gear(1, 8)
        self.assertTrue(any("undercut" in c for c in g.checks()))
        kinds = [s["type"] for s in g.tooth_space()["segments"]]
        self.assertGreaterEqual(kinds.count("spline"), 4)            # corner between trochoid and involute

    def test_standard_pair(self):
        m = G.mesh(G.Gear(2, 20), G.Gear(2, 40), face_width=20)
        self.assertAlmostEqual(m["centre_distance"], 60.0, places=6)
        self.assertAlmostEqual(m["contact_ratio"], 1.6352, places=3)
        self.assertEqual(m["tip_clearance"], [0.5, 0.5])
        self.assertEqual(m["warnings"], [])

    def test_shift_for_centre_distance(self):
        s = G.shift_for_centre_distance(2, 20, 40, 61.0)
        g1, g2 = G.Gear(2, 20, profile_shift=s["x1"]), G.Gear(2, 40, profile_shift=s["x2"])
        self.assertAlmostEqual(G.mesh(g1, g2)["zero_backlash_centre_distance"], 61.0, places=3)

    def test_helical_hands(self):
        w = G.mesh(G.Gear(2, 18, helix_angle=20), G.Gear(2, 36, helix_angle=20))["warnings"]
        self.assertTrue(any("opposite hands" in x for x in w))

    def test_internal_pair(self):
        m = G.mesh(G.Gear(1, 20), G.Gear(1, 60, internal=True))
        self.assertAlmostEqual(m["centre_distance"], 20.0)
        self.assertEqual(m["tip_clearance"], [0.25, 0.25])

    def test_planetary_assembly_closes(self):
        c = G.planetary(5.0, 3)["candidates"][0]
        self.assertEqual((c["sun"], c["planet"], c["ring"]), (18, 27, 72))
        zs, zp, zr, ph = c["sun"], c["planet"], c["ring"], c["phases"]
        frac = lambda v: v - math.floor(v + 1e-9)
        for p in ph["planets"]:
            th, phi, pr = math.radians(p["carrier_angle"]), math.radians(p["rotation"]), math.radians(ph["ring"])
            self.assertAlmostEqual(frac(th * zs / (2 * math.pi) + (th + math.pi - phi) * zp / (2 * math.pi)), 0.5, 6)
            self.assertAlmostEqual(frac((th - pr) * zr / (2 * math.pi) - (th - phi) * zp / (2 * math.pi)), 0.5, 6)

    def test_rack_tooth(self):
        rk = G.rack_profile(2, 3, backlash=0.1)
        xs = sorted(x0 + (0 - y0) * (x1 - x0) / (y1 - y0) for s in rk["segments"] if s["type"] == "line"
                    for (x0, y0), (x1, y1) in [s["points"]] if y0 * y1 < 0)
        self.assertAlmostEqual(xs[1] - xs[0], math.pi - 0.05, places=9)
        self.assertLess(_gap(rk), 1e-9)

    def test_default_shifts(self):
        d = api.design({"kind": "pair", "module": 1, "teeth": [12, 30]})
        self.assertAlmostEqual(d["gear1"]["x"], -d["gear2"]["x"])
        self.assertAlmostEqual(d["mesh"]["centre_distance"], 21.0, places=6)
        self.assertEqual(d["mesh"]["warnings"], [])


class BevelGears(unittest.TestCase):
    def test_pitch_angles_and_proportions(self):
        p, w = bevel.BevelGear(2, 16, 24), bevel.BevelGear(2, 24, 16)
        self.assertAlmostEqual(math.degrees(p.delta), math.degrees(math.atan(16 / 24)), places=9)
        self.assertAlmostEqual(p.ha + w.ha, 2.0 * 2, places=9)          # Gleason working depth 2 m
        self.assertAlmostEqual(p.s_e + w.s_e, math.pi * 2, places=9)
        self.assertAlmostEqual(p.R_e, w.R_e, places=9)

    def test_spiral_sections(self):
        g = bevel.BevelGear(2, 20, 20, spiral_angle=35, hand="right")
        R = g.section_radii()
        self.assertGreater(g.phi(R[-1]), g.phi(R[0]))                  # right hand: heel turned CCW
        self.assertAlmostEqual(math.degrees(g.spiral_angle_at(g.R_m)), 35.0, places=6)
        for r in R:
            self.assertGreater(g._root_land(r), 0.1 * g.m * r / g.R_e - 1e-9)


if __name__ == "__main__":
    unittest.main()
