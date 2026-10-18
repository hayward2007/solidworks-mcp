"""Straight and spiral bevel gear geometry (no CAD dependency). Units: mm, degrees outside.

Frame: gear axis = +Z, pitch-cone apex at the origin, the gear body at +Z (toe nearer the
apex, heel farther). Transverse tooth sections are Tredgold back-cone virtual spur gears
(z_v = z / cos(delta)) scaled with the cone distance (tip and root cones through the apex:
converging depth). Spiral teeth follow a circular-arc tooth trace (face-mill cutter radius
r_c) in the developed pitch cone.

Basis
- Pitch angles, cone distances, Gleason tooth proportions: ANSI/AGMA 2005 (Gleason system)
  as tabulated in the KHK Gear Technical Reference; 'standard' system: h_a = (1 + x) m,
  h_f = (1.25 - x) m.
- Face width default: min(R_e / 3, 10 m) [heur AGMA].
- Hand (AGMA): right hand = the outer half of a tooth is inclined clockwise as seen by an
  observer looking at the face of the gear (from the apex). In this frame: the tooth-space
  angle about +Z increases from toe to heel.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .geometry import Gear, resample, split_corners

Vec = Tuple[float, float, float]
# nominal face-mill cutter radii (inch diameters 1/2 ... 18 -> radius in mm) [cat Gleason]
CUTTER_RADII = tuple(round(d * 25.4 / 2, 3) for d in (0.5, 1.1, 1.5, 2, 3.5, 5, 6, 7.5, 9, 12, 18))


class BevelGear:
    def __init__(self, module: float, teeth: int, mate_teeth: int, shaft_angle: float = 90.0,
                 face_width: Optional[float] = None, pressure_angle: float = 20.0,
                 spiral_angle: float = 0.0, cutter_radius: Optional[float] = None, hand: str = "right",
                 system: str = "gleason", profile_shift: float = 0.0, backlash: float = 0.0,
                 is_pinion: Optional[bool] = None):
        self.m = float(module)                     # outer transverse module (heel)
        self.z, self.z_mate = int(teeth), int(mate_teeth)
        self.shaft_angle = float(shaft_angle)
        self.alpha_n = math.radians(pressure_angle)
        self.pressure_angle = float(pressure_angle)
        self.beta_m = math.radians(abs(spiral_angle))
        self.spiral_angle = abs(float(spiral_angle))
        self.hand = "left" if str(hand).lower().startswith("l") else "right"
        self.system = system.lower()
        self.backlash = max(float(backlash), 0.0)
        S = math.radians(self.shaft_angle)
        # pitch angle: tan(delta1) = sin(S) / (z2/z1 + cos(S))
        self.delta = math.atan2(math.sin(S), self.z_mate / self.z + math.cos(S))
        self.delta_mate = S - self.delta
        self.r_e = self.m * self.z / 2                         # outer pitch radius
        self.R_e = self.r_e / math.sin(self.delta)            # outer cone distance
        b_default = min(self.R_e / 3, 10 * self.m)
        self.b = float(face_width) if face_width else b_default
        self.face_width_basis = "[req]" if face_width else "[heur AGMA] min(R_e/3, 10 m)"
        self.R_i = self.R_e - self.b
        self.R_m = self.R_e - self.b / 2
        self.z_v = self.z / math.cos(self.delta)
        pinion = (self.z <= self.z_mate) if is_pinion is None else bool(is_pinion)
        self.is_pinion = pinion
        # tooth proportions at the heel (outer transverse module)
        m = self.m
        if self.system == "gleason":
            u = (self.z_mate * math.cos(self.delta)) / (self.z * math.cos(self.delta_mate))   # for gear 1 = this
            # formulas give the gear (larger) addendum; the pinion takes the rest of the working depth
            if self.beta_m > 0:
                work, whole = 1.700 * m, 1.888 * m
                ha_gear = 0.460 * m + 0.390 * m / max(u, 1 / u)
            else:
                work, whole = 2.000 * m, 2.188 * m + 0.051
                ha_gear = 0.540 * m + 0.460 * m / max(u, 1 / u)
            self.ha = (work - ha_gear) if pinion else ha_gear
            if self.z == self.z_mate:
                self.ha = work / 2
            self.hf = whole - self.ha
            # balanced thickness: the pinion gains what the gear loses (K factor = 0)
            d_ha = self.ha - work / 2
            self.s_e = math.pi * m / 2 + 2 * d_ha * math.tan(self.alpha_n) / math.cos(self.beta_m) - self.backlash / 2
            self.basis = "Gleason proportions (ANSI/AGMA 2005, KHK tables), Tredgold sections"
        else:
            x = float(profile_shift)
            self.ha = (1 + x) * m
            self.hf = (1.25 - x) * m
            self.s_e = m * (math.pi / 2 + 2 * x * math.tan(self.alpha_n) / math.cos(self.beta_m)) - self.backlash / 2
            self.basis = "standard proportions h_a = (1+x) m, h_f = (1.25-x) m, Tredgold sections"
        self.theta_a = math.atan(self.ha / self.R_e)          # face angle increment (apex-converging)
        self.theta_f = math.atan(self.hf / self.R_e)
        # spiral trace (developed pitch cone, polar (R, theta)); mean point at theta = 0
        if self.beta_m > 0:
            if cutter_radius:
                self.r_c = float(cutter_radius)
                self.cutter_basis = "[req]"
            else:
                self.r_c = next((c for c in CUTTER_RADII if c >= 1.0 * self.R_m), CUTTER_RADII[-1])
                self.cutter_basis = "[cat] smallest nominal face-mill cutter radius >= R_m"
            t = (math.cos(self.beta_m), math.sin(self.beta_m))   # outward tangent at the mean point (RH)
            n = (-t[1], t[0])
            c = (self.R_m + self.r_c * n[0], self.r_c * n[1])
            self._d = math.hypot(*c)
            self._phi_c = math.atan2(c[1], c[0])
            g_m = self._gamma(self.R_m)
            self._branch = 1 if abs(self._phi_c + g_m) < abs(self._phi_c - g_m) else -1
        else:
            self.r_c = None
            self.cutter_basis = None
        # cutter edge radius: ISO 53 A (0.38 m) unless the root land closes somewhere along the
        # face; then the largest radius that keeps a root land >= 0.1 m [heur], same in all sections
        self.rho_c = 0.38
        for rho in (0.38, 0.30, 0.25, 0.20, 0.15, 0.10):
            self.rho_c = rho
            if min(self._root_land(R) / (self.m * R / self.R_e) for R in self.section_radii()) >= 0.1:
                break

    # ---- spiral trace -------------------------------------------------------------------
    def _gamma(self, R: float) -> float:
        c = (R * R + self._d ** 2 - self.r_c ** 2) / (2 * R * self._d)
        return math.acos(max(-1.0, min(1.0, c)))

    def theta(self, R: float) -> float:
        """Developed angle of the tooth trace (right hand; mean point at 0)."""
        if self.beta_m == 0:
            return 0.0
        return self._phi_c + self._branch * self._gamma(R)

    def phi(self, R: float) -> float:
        """Angle about +Z of the tooth-space centre at cone distance R."""
        th = self.theta(R) / math.sin(self.delta)
        return th if self.hand == "right" else -th

    def spiral_angle_at(self, R: float) -> float:
        if self.beta_m == 0:
            return 0.0
        v = (R * R + self.r_c ** 2 - self._d ** 2) / (2 * R * self.r_c)
        return math.asin(max(-1.0, min(1.0, abs(v))))

    # ---- frames ----------------------------------------------------------------------
    def g(self, p: float) -> Vec:
        sd, cd = math.sin(self.delta), math.cos(self.delta)
        return (sd * math.cos(p), sd * math.sin(p), cd)

    def bvec(self, p: float) -> Vec:
        sd, cd = math.sin(self.delta), math.cos(self.delta)
        return (cd * math.cos(p), cd * math.sin(p), -sd)

    @staticmethod
    def et(p: float) -> Vec:
        return (-math.sin(p), math.cos(p), 0.0)

    # ---- sections ----------------------------------------------------------------------
    def section_gear(self, R: float) -> Gear:
        """Virtual (Tredgold) spur/helical gear of the transverse section at cone distance R."""
        k = R / self.R_e
        beta = self.spiral_angle_at(R)
        mt = self.m * k
        mn = mt * math.cos(beta)
        s_t = self.s_e * k
        x = (s_t / mt - math.pi / 2) / (2 * math.tan(self.alpha_n))
        ha, hf = self.ha * k, self.hf * k
        return Gear(mn, self.z_v, self.pressure_angle, math.degrees(beta), "right", x,
                    addendum_coeff=ha / mn - x, dedendum_coeff=hf / mn + x, virtual=True,
                    root_fillet_coeff=getattr(self, "rho_c", 0.38))

    def _root_land(self, R: float) -> float:
        vg = self.section_gear(R)
        theta_root, _ = vg._external_half(vg.ra + 0.6 * self.m * R / self.R_e)
        return 2 * vg.rf * math.sin(theta_root)

    def section(self, R: float, n_max: int = 24) -> Dict:
        """Closed tooth-space outline at cone distance R in 3D (mm): root line, right flank
        (root -> top), top line, left flank (top -> root). Corners for loft guide curves."""
        vg = self.section_gear(R)
        k = R / self.R_e
        r_out = vg.ra + 0.6 * self.m * k
        theta_root, curve = vg._external_half(r_out)
        # one spline per flank, from the root-arc end to the top (+Y frame of the virtual gear)
        flank = resample(curve, max_count=n_max)
        p = self.phi(R)
        P = tuple(R * c for c in self.g(p))
        rho = R * math.tan(self.delta)
        bv, ev = self.bvec(p), self.et(p)
        V = tuple(P[i] - rho * bv[i] for i in range(3))

        def to3d(pt, side):
            # virtual frame: +Y = radial (b), +X = tangential; side +1 right flank, -1 left flank
            x, y = pt
            return tuple(V[i] + y * bv[i] + side * x * ev[i] for i in range(3))
        right = [to3d(q, 1) for q in flank]
        left = [to3d(q, -1) for q in reversed(flank)]
        return {"R": R, "right": right, "left": left,
                "corners": [right[0], right[-1], left[0], left[-1]],   # root R, top R, top L, root L
                "spiral_angle_deg": math.degrees(self.spiral_angle_at(R)), "phi_deg": math.degrees(p)}

    def section_radii(self, n: Optional[int] = None) -> List[float]:
        """Cone distances of the loft sections, extended beyond toe and heel."""
        n = n or (9 if self.beta_m > 0 else 3)
        a, b = self.R_i - 0.75 * self.m * self.R_i / self.R_e, self.R_e + 0.9 * self.m
        return [a + (b - a) * i / (n - 1) for i in range(n)]

    # ---- blank -------------------------------------------------------------------------
    def blank_profile(self, bore: float = 0.0) -> List[Tuple[float, float]]:
        """Meridian half-section (r, z) of the turned blank: front cone (toe), face cone,
        back cone (heel), flat back and front faces; cones normal to the pitch cone [std]."""
        sd, cd = math.sin(self.delta), math.cos(self.delta)

        def on_pitch(R, h):            # point at cone distance R, offset h along +b
            return (R * sd + h * cd, R * cd - h * sd)
        toe_tip = on_pitch(self.R_i, self.ha * self.R_i / self.R_e)
        heel_tip = on_pitch(self.R_e, self.ha)
        # front and back cones run inward along -b down to 1 m below the root circle [neutral]
        depth_toe = (self.ha + self.hf) * self.R_i / self.R_e + self.m * self.R_i / self.R_e
        depth_heel = self.ha + self.hf + self.m
        front = (toe_tip[0] - depth_toe * cd, toe_tip[1] + depth_toe * sd)
        back = (heel_tip[0] - depth_heel * cd, heel_tip[1] + depth_heel * sd)
        r_in = bore / 2 if bore else 0.0
        if front[0] <= r_in + 0.5 * self.m or back[0] <= r_in + 0.5 * self.m:
            raise ValueError("bore too large for this bevel gear")
        return [(r_in, front[1]), front, toe_tip, heel_tip, back, (r_in, back[1])]

    # ---- reporting ---------------------------------------------------------------------
    def summary(self) -> Dict:
        out = {"type": "spiral bevel" if self.beta_m else "straight bevel", "z": self.z,
               "z_mate": self.z_mate, "m_outer": self.m, "shaft_angle_deg": self.shaft_angle,
               "pitch_angle_deg": round(math.degrees(self.delta), 4),
               "d_outer": round(2 * self.r_e, 4), "R_e": round(self.R_e, 4), "face_width": round(self.b, 4),
               "face_width_basis": self.face_width_basis, "addendum": round(self.ha, 4),
               "dedendum": round(self.hf, 4),
               "da_outer": round(2 * (self.r_e + self.ha * math.cos(self.delta)), 4),
               "face_angle_deg": round(math.degrees(self.delta + self.theta_a), 4),
               "root_angle_deg": round(math.degrees(self.delta - self.theta_f), 4),
               "z_virtual": round(self.z_v, 3), "edge_radius_coeff": self.rho_c, "basis": self.basis}
        if self.beta_m:
            out.update({"hand": self.hand, "spiral_angle_mean_deg": self.spiral_angle,
                        "cutter_radius": self.r_c, "cutter_basis": self.cutter_basis,
                        "spiral_angle_toe_deg": round(math.degrees(self.spiral_angle_at(self.R_i)), 2),
                        "spiral_angle_heel_deg": round(math.degrees(self.spiral_angle_at(self.R_e)), 2)})
        return out

    def checks(self) -> List[str]:
        w = []
        if self.b > self.R_e / 3 + 1e-9:
            w.append("face width %.2f > R_e/3 = %.2f [heur AGMA]" % (self.b, self.R_e / 3))
        if self.b > 10 * self.m + 1e-9:
            w.append("face width %.2f > 10 m [heur AGMA]" % self.b)
        vg = self.section_gear(self.R_m)
        w.extend("mean section: " + c for c in vg.checks() if "undercut" in c or "pointed" in c)
        if self.beta_m and self.r_c < 0.9 * self.R_m:
            w.append("cutter radius below 0.9 R_m: large spiral-angle variation")
        return w


def bevel_mesh(g1: BevelGear, g2: BevelGear) -> Dict:
    """Pair data for two bevel gears built with apexes at their part origins.
    Layout: gear 1 axis +Z, gear 2 axis along +X (shaft angle 90) with coincident apexes;
    gear 2 part frame maps X -> -Z, Y -> +Y, Z -> +X. Phases are rotations about each part's
    own Z axis so that the meshes close at the mean section."""
    w = []
    if abs(g1.m - g2.m) > 1e-9 or g1.z != g2.z_mate or g2.z != g1.z_mate:
        w.append("modules or tooth counts do not pair")
    if abs(g1.delta + g2.delta - math.radians(g1.shaft_angle)) > 1e-6:
        w.append("pitch angles do not add up to the shaft angle")
    if g1.beta_m != g2.beta_m:
        w.append("spiral angles differ")
    if g1.beta_m and g1.hand == g2.hand:
        w.append("spiral bevel pair needs opposite hands")
    if abs(g1.shaft_angle - 90.0) > 1e-9:
        w.append("layout and mesh check assume a 90 deg shaft angle")
    phase2 = (math.pi - math.pi / g2.z) % (2 * math.pi / g2.z)
    # virtual spur pair at the heel for the contact ratio
    v1 = Gear(g1.m * math.cos(g1.beta_m), g1.z_v, g1.pressure_angle, math.degrees(g1.beta_m), "right",
              addendum_coeff=g1.ha / (g1.m * math.cos(g1.beta_m)), virtual=True)
    v2 = Gear(g2.m * math.cos(g2.beta_m), g2.z_v, g2.pressure_angle, math.degrees(g2.beta_m), "right",
              addendum_coeff=g2.ha / (g2.m * math.cos(g2.beta_m)), virtual=True)
    ga1 = math.sqrt(max(v1.ra ** 2 - v1.rb ** 2, 0)); ga2 = math.sqrt(max(v2.ra ** 2 - v2.rb ** 2, 0))
    eps = (ga1 + ga2 - (v1.r + v2.r) * math.sin(v1.alpha_t)) / v1.pbt
    return {"ratio": round(g2.z / g1.z, 6), "phase_deg": [0.0, round(math.degrees(phase2), 5)],
            "virtual_contact_ratio": round(eps, 4),
            "layout": "apexes coincident at the origin; gear 1 axis +Z, gear 2 axis +X; rotate gear 2 "
                      "by phase_deg about its own axis", "warnings": w}
