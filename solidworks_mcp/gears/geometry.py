"""Involute cylindrical gear geometry for CAD (no SolidWorks dependency).

Units: mm and degrees at the interface, radians inside.

Design basis
- ISO 21771:2007 cylindrical involute gears and gear pairs (geometry, profile shift,
  centre distance, contact ratio, tip alteration)
- ISO 53:1998 basic rack tooth profiles A-D (addendum, dedendum, root fillet)
- ISO 54 / DIN 780 module series
- KHK Gear Technical Reference for internal gears (profile shift x > 0 moves the internal
  profile away from the axis: d_a = d - 2 m (h_a* - x), s = m (pi/2 - 2 x tan a)).

The external tooth space is generated, not drawn: every point of the counterpart rack
(cutter) generates the gear where its normal passes through the pitch point (law of
gearing). The straight cutter flank gives the involute, the cutter tip fillet gives the
trochoidal root fillet, and undercut appears by itself when the trochoid cuts the involute.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[float, float]

# ISO 53 basic rack profiles: addendum h_aP*, dedendum h_fP*, root fillet rho_fP* (x module)
ISO53_PROFILES = {
    "A": (1.0, 1.25, 0.38),
    "B": (1.0, 1.25, 0.30),
    "C": (1.0, 1.25, 0.25),
    "D": (1.0, 1.40, 0.39),
}
# Preferred modules: ISO 54 series I/II (m >= 1) and DIN 780 / JIS B 1701 (m < 1)
MODULES_FIRST = (0.5, 0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20, 25, 32, 40, 50)
MODULES_SECOND = (0.55, 0.7, 0.9, 1.125, 1.375, 1.75, 2.25, 2.75, 3.5, 4.5, 5.5, 7, 9, 11, 14, 18, 22,
                  28, 36, 45)


# ----------------------------------------------------------------------------------------
# small math helpers
# ----------------------------------------------------------------------------------------
def inv(a: float) -> float:
    """Involute function inv(a) = tan(a) - a."""
    return math.tan(a) - a


def inv_inverse(v: float) -> float:
    """Angle a (rad) with inv(a) = v, Newton iteration (|error| < 1e-14)."""
    if v <= 0.0:
        return 0.0
    a = min((3.0 * v) ** (1.0 / 3.0), 1.4)
    for _ in range(60):
        t = math.tan(a)
        step = (t - a - v) / (t * t)
        a = min(max(a - step, 1e-9), 1.5)
        if abs(step) < 1e-15:
            break
    return a


def nearest_module(m: float) -> float:
    """Closest preferred module, series I first (ISO 54 / DIN 780)."""
    best = min(MODULES_FIRST, key=lambda q: abs(q - m))
    alt = min(MODULES_SECOND, key=lambda q: abs(q - m))
    return alt if abs(alt - m) < 0.5 * abs(best - m) else best


def _rot(p: Point, a: float) -> Point:
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def _seg_intersect(a: Point, b: Point, c: Point, d: Point) -> Optional[Point]:
    """Intersection point of segments ab and cd (None if they do not cross)."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < 1e-18:
        return None
    qp = (c[0] - a[0], c[1] - a[1])
    t = (qp[0] * s[1] - qp[1] * s[0]) / den
    u = (qp[0] * r[1] - qp[1] * r[0]) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (a[0] + t * r[0], a[1] + t * r[1])
    return None


def remove_loops(pts: Sequence[Point]) -> Tuple[List[Point], int]:
    """Cut self-intersection loops out of a polyline (undercut swallowtails).
    Returns (polyline, index of the corner point or -1)."""
    out = list(pts)
    corner = -1
    for _ in range(8):
        n = len(out)
        boxes = [(min(out[i][0], out[i + 1][0]), max(out[i][0], out[i + 1][0]),
                  min(out[i][1], out[i + 1][1]), max(out[i][1], out[i + 1][1])) for i in range(n - 1)]
        hit = None
        for i in range(n - 3):
            bi = boxes[i]
            for j in range(n - 2, i + 1, -1):
                bj = boxes[j]
                if bj[0] > bi[1] or bj[1] < bi[0] or bj[2] > bi[3] or bj[3] < bi[2]:
                    continue
                p = _seg_intersect(out[i], out[i + 1], out[j], out[j + 1])
                if p is not None and j > i + 1:
                    hit = (i, j, p)
                    break
            if hit:
                break
        if not hit:
            break
        i, j, p = hit
        out = out[:i + 1] + [p] + out[j + 1:]
        corner = i + 1
    return out, corner


def clip_at_radius(pts: Sequence[Point], radius: float) -> List[Point]:
    """Keep the polyline up to its first crossing of the circle |p| = radius (outward)."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        ra, rb = math.hypot(*a), math.hypot(*b)
        if rb >= radius > ra:
            # solve |a + t (b - a)| = radius
            dx, dy = b[0] - a[0], b[1] - a[1]
            A = dx * dx + dy * dy
            B = 2 * (a[0] * dx + a[1] * dy)
            C = a[0] ** 2 + a[1] ** 2 - radius ** 2
            t = (-B + math.sqrt(max(B * B - 4 * A * C, 0.0))) / (2 * A)
            out.append((a[0] + t * dx, a[1] + t * dy))
            return out
        out.append(b)
    return out


def split_corners(pts: Sequence[Point], max_turn_deg: float = 12.0) -> List[List[Point]]:
    """Split a polyline into tangent-continuous pieces at corners."""
    pieces, cur = [], [pts[0]]
    lim = math.radians(max_turn_deg)
    for k in range(1, len(pts) - 1):
        cur.append(pts[k])
        a = math.atan2(pts[k][1] - pts[k - 1][1], pts[k][0] - pts[k - 1][0])
        b = math.atan2(pts[k + 1][1] - pts[k][1], pts[k + 1][0] - pts[k][0])
        turn = abs((b - a + math.pi) % (2 * math.pi) - math.pi)
        if turn > lim:
            pieces.append(cur)
            cur = [pts[k]]
    cur.append(pts[-1])
    pieces.append(cur)
    return [p for p in pieces if len(p) >= 2]


def resample(pts: Sequence[Point], max_turn_deg: float = 3.0, max_count: int = 60,
             min_count: int = 10) -> List[Point]:
    """Pick spline through-points from a dense smooth polyline: a point whenever the tangent
    turned by max_turn_deg or the arc length reached L/(min_count - 1). With the defaults a
    cubic spline through the points stays within about 5 um of the curve up to module 10."""
    if len(pts) <= min_count:
        return list(pts)
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    max_len = total / (min_count - 1)
    lim = math.radians(max_turn_deg)
    out = [pts[0]]
    acc_len, acc_turn = 0.0, 0.0
    prev_dir = math.atan2(pts[1][1] - pts[0][1], pts[1][0] - pts[0][0])
    for k in range(1, len(pts) - 1):
        acc_len += seg[k - 1]
        d = math.atan2(pts[k + 1][1] - pts[k][1], pts[k + 1][0] - pts[k][0])
        acc_turn += abs((d - prev_dir + math.pi) % (2 * math.pi) - math.pi)
        prev_dir = d
        if acc_turn >= lim or acc_len >= max_len * 0.999:
            out.append(pts[k])
            acc_len, acc_turn = 0.0, 0.0
    out.append(pts[-1])
    if len(out) > max_count:              # thin out evenly, keep the ends
        step = (len(out) - 1) / (max_count - 1)
        out = [out[round(i * step)] for i in range(max_count)]
    # drop a near-duplicate before the end point (spline knots too close)
    if len(out) > 2 and math.hypot(out[-1][0] - out[-2][0], out[-1][1] - out[-2][1]) < 0.1 * max_len:
        out.pop(-2)
    return out


def polygon_area(pts: Sequence[Point]) -> float:
    """Signed area (CCW positive) of a closed polygon given without repeating the first point."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(pts, list(pts[1:]) + [pts[0]]):
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def arc_points(center: Point, radius: float, a0: float, a1: float, n: int = 24) -> List[Point]:
    return [(center[0] + radius * math.cos(a0 + (a1 - a0) * i / n),
             center[1] + radius * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


# ----------------------------------------------------------------------------------------
# cylindrical gear
# ----------------------------------------------------------------------------------------
class Gear:
    """Spur or helical, external or internal involute gear.

    module          normal module m_n [std ISO 54]
    teeth           number of teeth z (always positive; use internal=True for ring gears)
    pressure_angle  normal pressure angle alpha_n, deg [std ISO 53: 20]
    helix_angle     helix angle beta at the reference cylinder, deg (0 = spur)
    hand            'right' or 'left' (helical only)
    profile_shift   x (KHK sign convention for internal gears, see module docstring)
    backlash        circumferential backlash of the mesh at the reference circle, mm;
                    this gear's teeth are thinned by half of it
    tip_shortening  tip alteration k (x module, >= 0 shortens the teeth)
    profile         ISO 53 basic rack 'A' (default), 'B', 'C' or 'D'
    addendum_coeff, dedendum_coeff  override h_aP*, h_fP* of the profile (x m_n)
    virtual         allow a non-integer tooth count (virtual spur gear of a bevel section)
    """

    def __init__(self, module: float, teeth: int, pressure_angle: float = 20.0,
                 helix_angle: float = 0.0, hand: str = "right", profile_shift: float = 0.0,
                 backlash: float = 0.0, internal: bool = False, tip_shortening: float = 0.0,
                 profile: str = "A", addendum_coeff: Optional[float] = None,
                 dedendum_coeff: Optional[float] = None, virtual: bool = False,
                 root_fillet_coeff: Optional[float] = None):
        if module <= 0 or float(teeth) < 3:
            raise ValueError("module must be > 0 and teeth >= 3")
        if profile.upper() not in ISO53_PROFILES:
            raise ValueError("profile must be one of A, B, C, D (ISO 53)")
        self.module = float(module)
        self.teeth = float(teeth) if virtual else int(teeth)
        self.pressure_angle = float(pressure_angle)
        self.helix_angle = abs(float(helix_angle))
        self.hand = "left" if str(hand).lower().startswith("l") else "right"
        self.profile_shift = float(profile_shift)
        self.backlash = max(float(backlash), 0.0)
        self.internal = bool(internal)
        self.tip_shortening = float(tip_shortening)
        self.profile = profile.upper()
        self.ha_c, self.hf_c, self.rho_c = ISO53_PROFILES[self.profile]
        if addendum_coeff is not None:
            self.ha_c = float(addendum_coeff)
        if dedendum_coeff is not None:
            self.hf_c = float(dedendum_coeff)
        if root_fillet_coeff is not None:
            self.rho_c = float(root_fillet_coeff)

        self.mn = self.module
        self.alpha_n = math.radians(self.pressure_angle)
        self.beta = math.radians(self.helix_angle)
        self.mt = self.mn / math.cos(self.beta)
        self.alpha_t = math.atan(math.tan(self.alpha_n) / math.cos(self.beta))
        self.r = self.teeth * self.mt / 2
        self.rb = self.r * math.cos(self.alpha_t)
        self.beta_b = math.atan(math.tan(self.beta) * math.cos(self.alpha_t))
        self.pt = math.pi * self.mt
        self.pbt = self.pt * math.cos(self.alpha_t)
        self.thinning = self.backlash / 2
        x, k, mn = self.profile_shift, self.tip_shortening, self.mn
        if self.internal:
            self.ra = self.r - mn * (self.ha_c - x - k)
            self.rf = self.r + mn * (self.hf_c + x)
            self.s = self.mt * (math.pi / 2 - 2 * x * math.tan(self.alpha_n)) - self.thinning
        else:
            self.ra = self.r + mn * (self.ha_c + x - k)
            self.rf = self.r - mn * (self.hf_c - x)
            self.s = self.mt * (math.pi / 2 + 2 * x * math.tan(self.alpha_n)) - self.thinning
        self.notes: List[str] = []
        self.tip_clamped = False
        if self.internal and self.ra < self.rb * 1.0005:
            self.notes.append("internal tip circle was inside the base circle; tips shortened to "
                              "d_a = %.3f (increase x or teeth to avoid this)" % (2 * self.rb * 1.0005))
            self.ra = self.rb * 1.0005
            self.tip_clamped = True

    # ---- basic relations ------------------------------------------------------------------
    @property
    def d(self) -> float:
        return 2 * self.r

    @property
    def da(self) -> float:
        return 2 * self.ra

    @property
    def df(self) -> float:
        return 2 * self.rf

    @property
    def db(self) -> float:
        return 2 * self.rb

    @property
    def lead(self) -> Optional[float]:
        """Axial lead of the helix at the reference cylinder (mm)."""
        return None if self.beta == 0 else math.pi * self.d / math.tan(self.beta)

    def twist(self, length: float) -> float:
        """Rotation (rad, CCW about +Z positive) of the transverse profile over an axial
        length for this hand: right hand turns counter-clockwise when moving along +Z."""
        a = length * math.tan(self.beta) / self.r
        return a if self.hand == "right" else -a

    def half_thickness_angle(self, R: float) -> float:
        """Half tooth angle at radius R >= r_b (transverse)."""
        aR = math.acos(min(1.0, self.rb / R))
        if self.internal:
            return self.s / self.d - inv(self.alpha_t) + inv(aR)
        return self.s / self.d + inv(self.alpha_t) - inv(aR)

    def thickness_at(self, R: float) -> float:
        """Transverse arc tooth thickness at radius R."""
        return 2 * R * self.half_thickness_angle(R)

    @property
    def tip_thickness(self) -> float:
        return self.thickness_at(self.ra)

    @property
    def x_min_undercut(self) -> float:
        """Smallest profile shift without undercut for the ISO 53 cutter (ISO 21771 / DIN 3960)."""
        return (self.hf_c - self.rho_c * (1 - math.sin(self.alpha_n))
                - self.teeth * math.sin(self.alpha_t) ** 2 / (2 * math.cos(self.beta)))

    def checks(self) -> List[str]:
        """Warnings about this gear alone (empty list = fine)."""
        w = list(self.notes)
        mn = self.mn
        if not self.internal and self.profile_shift < self.x_min_undercut - 1e-9:
            w.append("undercut: x = %.3f < x_min = %.3f (root is weakened; raise x or teeth)"
                     % (self.profile_shift, self.x_min_undercut))
        sa = self.tip_thickness
        if sa <= 0:
            w.append("pointed teeth: tip thickness %.3f mm <= 0 (lower x or add tip_shortening)" % sa)
        elif sa < 0.25 * mn:
            w.append("thin tip: s_a = %.3f mm < 0.25 m [heur]" % sa)
        if self.helix_angle > 45:
            w.append("helix angle above 45 deg")
        if self.teeth < 6 and not self.internal:
            w.append("very few teeth (< 6)")
        return w

    def summary(self) -> Dict:
        """Key dimensions in mm (rounded) with their basis."""
        out = {
            "type": ("internal " if self.internal else "") + ("helical" if self.beta else "spur"),
            "z": self.teeth, "m_n": self.mn, "alpha_n_deg": self.pressure_angle,
            "beta_deg": self.helix_angle, "x": self.profile_shift,
            "d": round(self.d, 4), "d_a": round(self.da, 4), "d_f": round(self.df, 4),
            "d_b": round(self.db, 4), "s_t": round(self.s, 4), "s_a": round(self.tip_thickness, 4),
            "basis": "ISO 21771 geometry, ISO 53 profile %s, backlash share %.3f mm"
                     % (self.profile, self.thinning),
        }
        if self.beta:
            out.update({"hand": self.hand, "m_t": round(self.mt, 5),
                        "alpha_t_deg": round(math.degrees(self.alpha_t), 4),
                        "lead": round(self.lead, 3)})
        return out

    # ---- tooth space outline --------------------------------------------------------------
    def _external_half(self, r_out: float) -> Tuple[float, List[Point]]:
        """Right half of the tooth space centred on +Y, generated by the counterpart rack.
        Returns (root arc half angle, polyline from the root arc end out to r_out)."""
        mn, an, cb, r = self.mn, self.alpha_n, math.cos(self.beta), self.r
        tan_an, cos_an, sin_an = math.tan(an), math.cos(an), math.sin(an)
        y0 = r + self.profile_shift * mn                 # cutter datum line
        y_tip = y0 - self.hf_c * mn                      # cutter tip line = root circle
        w0 = math.pi * mn / 4 + self.thinning * cb / 2    # cutter half width at the datum (normal)

        def w_n(y):
            return w0 - (y0 - y) * tan_an

        rho = self.rho_c * mn
        rho_max = w_n(y_tip) / (1 / cos_an - tan_an)
        if rho > rho_max:
            rho = max(rho_max, 0.0)
            self.notes.append("cutter tip fillet reduced to %.3f mm (full round root)" % rho)
        yc = y_tip + rho
        xc = max(w_n(yc) - rho / cos_an, 0.0)
        samples = []                                     # cutter point + outward normal (normal section)
        nf = 60
        for i in range(nf + 1):
            ph = (math.pi / 2 - an) * i / nf
            samples.append((xc + rho * math.sin(ph), yc - rho * math.cos(ph), math.sin(ph), -math.cos(ph)))
        tx, ty = xc + rho * cos_an, yc - rho * sin_an
        y_top = r_out + mn
        length = (y_top - ty) / cos_an
        nl = 240
        for i in range(1, nl + 1):
            t = length * (i / nl) ** 1.2                 # denser near the root
            samples.append((tx + t * sin_an, ty + t * cos_an, cos_an, -sin_an))
        pts = []
        for px, py, nx, ny in samples:
            ptx = px / cb                                # transverse section of the cutter
            ntx, nty = nx * cb, ny
            ln = math.hypot(ntx, nty)
            ntx, nty = ntx / ln, nty / ln
            tt = (r - py) / nty                          # normal through the pitch point (0, r)
            sft = -ptx - tt * ntx                        # rack travel
            pts.append(_rot((ptx + sft, py), sft / r))   # gear turned by sft / r
        pts, _ = remove_loops(pts)
        pts = clip_at_radius(pts, r_out)
        return xc / cb / r, pts

    def _internal_half(self, r_in: float) -> Tuple[List[Point], Optional[Tuple[Point, Point, Point]], float]:
        """Right half of an internal-gear tooth space centred on +Y: involute flank from r_in
        to the fillet, circular root fillet [heur, approximates the shaper-cut root].
        Returns (flank polyline, fillet (centre, start, end) or None, root arc start angle)."""
        r, rb, at, mn = self.r, self.rb, self.alpha_t, self.mn
        e = self.pt - self.s                             # space width at the reference circle

        def eta(R):
            return e / (2 * r) + inv(at) - inv(math.acos(min(1.0, rb / R)))

        def pt(R):
            a = eta(R)
            return (R * math.sin(a), R * math.cos(a))

        r0 = max(rb, r_in)
        n = 160
        flank = []
        if r_in < rb:                                   # radial run-out inside the bore [neutral]
            flank.append((r_in * math.sin(eta(rb)), r_in * math.cos(eta(rb))))
        for i in range(n + 1):
            R = r0 + (self.rf - r0) * (1 - math.cos(math.pi * i / (2 * n)))
            flank.append(pt(R))
        rho = self.rho_c * mn

        def dist_to_flank(c):
            best = float("inf")
            for a, b in zip(flank, flank[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L2 = dx * dx + dy * dy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / L2))
                q = (a[0] + t * dx, a[1] + t * dy)
                best = min(best, math.hypot(c[0] - q[0], c[1] - q[1]))
            return best

        def centre(theta, rr):
            return ((self.rf - rr) * math.sin(theta), (self.rf - rr) * math.cos(theta))

        if dist_to_flank(centre(0.0, rho)) < rho:        # root too narrow: largest fitting radius
            lo, hi = 0.0, rho
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                if dist_to_flank(centre(0.0, mid)) >= mid:
                    lo = mid
                else:
                    hi = mid
            rho = lo
            self.notes.append("internal root fillet reduced to %.3f mm" % rho)
        if rho <= 1e-6:
            return flank, None, eta(self.rf)
        lo, hi = 0.0, eta(self.rf - rho)
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if dist_to_flank(centre(mid, rho)) > rho:
                lo = mid
            else:
                hi = mid
        theta_c = 0.5 * (lo + hi)
        c = centre(theta_c, rho)
        # tangent point on the flank = closest point; cut the flank there
        best, best_i, best_q = float("inf"), 0, flank[0]
        for i, (a, b) in enumerate(zip(flank, flank[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / L2))
            q = (a[0] + t * dx, a[1] + t * dy)
            dd = math.hypot(c[0] - q[0], c[1] - q[1])
            if dd < best:
                best, best_i, best_q = dd, i, q
        flank = flank[:best_i + 1] + [best_q]
        root_pt = (self.rf * math.sin(theta_c), self.rf * math.cos(theta_c))
        return flank, (c, best_q, root_pt), theta_c

    def tooth_space(self, extension: Optional[float] = None, clip: Optional[float] = None,
                    dense: bool = False) -> Dict:
        """Closed outline of one tooth space, centred on the +X axis (angle 0), as CAD segments.

        External gears: from the root circle out to r_a + extension (cut beyond the blank).
        Internal gears: from r_a - extension (inside the bore) out to the root circle.
        clip overrides the outer (external) / inner (internal) radius (used for areas);
        dense=True keeps the generated polylines instead of spline through-points.

        Segments (closed loop, counter-clockwise): {'type': 'arc', 'center', 'radius', 'start',
        'end', 'ccw'} and {'type': 'spline', 'points'}; points in mm.
        """
        ext = 0.5 * self.mn if extension is None else extension
        to_x = -math.pi / 2                               # +Y frame -> +X frame
        right: List[Dict] = []                           # chain in the +Y frame, from the centre line
        if not self.internal:
            r_out = clip if clip is not None else self.ra + ext
            theta_root, curve = self._external_half(r_out)
            if theta_root > 1e-9:
                right.append({"type": "arc", "center": (0.0, 0.0), "radius": self.rf,
                              "a0": math.pi / 2, "a1": math.pi / 2 - theta_root})
            for piece in split_corners(curve):
                right.append({"type": "spline", "points": piece})
            end = curve[-1]
            closing = {"type": "arc", "center": (0.0, 0.0), "radius": r_out,
                       "a0": math.atan2(end[1], end[0]), "a1": math.pi / 2}
            right.append(closing)
        else:
            r_in = clip if clip is not None else self.ra - ext
            flank, fillet, theta_c = self._internal_half(r_in)
            start = flank[0]
            right.append({"type": "arc", "center": (0.0, 0.0), "radius": math.hypot(*start),
                          "a0": math.pi / 2, "a1": math.atan2(start[1], start[0])})
            if r_in < self.rb and len(flank) > 2:
                right.append({"type": "line", "points": [flank[0], flank[1]]})
                flank = flank[1:]
            right.append({"type": "spline", "points": flank})
            if fillet:
                c, p0, p1 = fillet
                right.append({"type": "arc", "center": c, "radius": math.hypot(p0[0] - c[0], p0[1] - c[1]),
                              "a0": math.atan2(p0[1] - c[1], p0[0] - c[0]),
                              "a1": math.atan2(p1[1] - c[1], p1[0] - c[0])})
            if theta_c > 1e-9:
                right.append({"type": "arc", "center": (0.0, 0.0), "radius": self.rf,
                              "a0": math.pi / 2 - theta_c, "a1": math.pi / 2})
        return _closed_loop(right, to_x, resample_splines=not dense)

    def transverse_area(self, bore: float = 0.0, rim_diameter: Optional[float] = None) -> float:
        """Exact transverse section area (mm2) of the toothed blank, for volume checks.
        External: tip circle minus tooth spaces minus bore. Internal: rim disc minus the
        tip-circle bore minus tooth spaces."""
        loop = self.tooth_space(clip=self.ra, dense=True)
        space = abs(polygon_area(loop_points(loop, 48)))
        if self.internal:
            if not rim_diameter:
                raise ValueError("rim_diameter is required for internal gears")
            return math.pi * (rim_diameter ** 2 / 4 - self.ra ** 2) - self.teeth * space
        return math.pi * (self.ra ** 2 - bore ** 2 / 4) - self.teeth * space


def _closed_loop(right: List[Dict], to_x: float, resample_splines: bool = True) -> Dict:
    """Mirror a right-half chain (+Y frame, starting and ending on the centre line) into a
    closed loop and rotate it so the space is centred on +X."""
    def tr(p):
        return _rot(p, to_x)

    def seg_out(s, mirror=False, reverse=False):
        if s["type"] == "arc":
            cx, cy = s["center"]
            a0, a1 = s["a0"], s["a1"]
            if mirror:
                cx, a0, a1 = -cx, math.pi - a0, math.pi - a1
            if reverse:
                a0, a1 = a1, a0
            c = tr((cx, cy))
            r = s["radius"]
            p0 = tr((cx + r * math.cos(a0), cy + r * math.sin(a0)))
            p1 = tr((cx + r * math.cos(a1), cy + r * math.sin(a1)))
            return {"type": "arc", "center": c, "radius": r, "start": p0, "end": p1, "ccw": a1 > a0,
                    "a0": a0 + to_x, "a1": a1 + to_x}
        pts = s["points"]
        if mirror:
            pts = [(-x, y) for x, y in pts]
        if reverse:
            pts = list(reversed(pts))
        pts = [tr(p) for p in pts]
        return {"type": s["type"], "points": pts}

    # right chain runs centre(inner) -> ... -> centre(outer) on the right; the loop is
    # right chain forward + mirrored chain backwards (splines resampled first: exact mirror)
    for s in right:
        if s["type"] == "spline" and resample_splines:
            s["points"] = resample(s["points"])
    segs = [seg_out(s) for s in right] + [seg_out(s, mirror=True, reverse=True) for s in reversed(right)]
    # merge the two centre-line arcs that meet on the axis into single arcs
    merged: List[Dict] = []
    for s in segs:
        if (merged and s["type"] == "arc" and merged[-1]["type"] == "arc"
                and abs(merged[-1]["radius"] - s["radius"]) < 1e-9
                and math.hypot(merged[-1]["center"][0] - s["center"][0], merged[-1]["center"][1] - s["center"][1]) < 1e-9
                and (merged[-1]["ccw"] == s["ccw"])):
            m = merged[-1]
            merged[-1] = {"type": "arc", "center": m["center"], "radius": m["radius"], "start": m["start"],
                          "end": s["end"], "ccw": m["ccw"], "a0": m["a0"], "a1": m["a1"] + (s["a1"] - s["a0"])}
        else:
            merged.append(s)
    if (len(merged) > 1 and merged[0]["type"] == "arc" and merged[-1]["type"] == "arc"
            and abs(merged[0]["radius"] - merged[-1]["radius"]) < 1e-9
            and math.hypot(merged[0]["center"][0] - merged[-1]["center"][0],
                           merged[0]["center"][1] - merged[-1]["center"][1]) < 1e-9
            and merged[0]["ccw"] == merged[-1]["ccw"]):
        last, first = merged.pop(-1), merged[0]
        merged[0] = {"type": "arc", "center": first["center"], "radius": first["radius"], "start": last["start"],
                     "end": first["end"], "ccw": first["ccw"], "a0": last["a0"],
                     "a1": last["a0"] + (last["a1"] - last["a0"]) + (first["a1"] - first["a0"])}
    return {"segments": merged}


def loop_points(loop: Dict, arc_n: int = 24) -> List[Point]:
    """Dense polygon of a closed segment loop (for areas and plots)."""
    out: List[Point] = []
    for s in loop["segments"]:
        if s["type"] == "arc":
            pts = arc_points(s["center"], s["radius"], s["a0"], s["a1"], arc_n)
        else:
            pts = s["points"]
        out.extend(pts[:-1])
    return out


# ----------------------------------------------------------------------------------------
# gear pairs
# ----------------------------------------------------------------------------------------
def working_pressure_angle(g1: Gear, g2: Gear) -> float:
    """Transverse working pressure angle (rad) for zero-backlash mesh of the given shifts."""
    tan_an = math.tan(g1.alpha_n)
    if g2.internal:
        v = 2 * tan_an * (g2.profile_shift - g1.profile_shift) / (g2.teeth - g1.teeth) + inv(g1.alpha_t)
    else:
        v = 2 * tan_an * (g1.profile_shift + g2.profile_shift) / (g1.teeth + g2.teeth) + inv(g1.alpha_t)
    return inv_inverse(v)


def shift_for_centre_distance(module: float, z1: int, z2: int, centre_distance: float,
                              pressure_angle: float = 20.0, helix_angle: float = 0.0,
                              internal: bool = False) -> Dict:
    """Profile shift sum needed for a required centre distance (ISO 21771), and a split that
    keeps the pinion free of undercut, otherwise equal shares [neutral]."""
    an, b = math.radians(pressure_angle), math.radians(helix_angle)
    mt = module / math.cos(b)
    at = math.atan(math.tan(an) / math.cos(b))
    zs = (z2 - z1) if internal else (z1 + z2)
    a0 = zs * mt / 2
    c = zs * mt * math.cos(at) / (2 * centre_distance)
    if not 0 < c < 1:
        raise ValueError("centre distance out of range")
    awt = math.acos(c)
    x_sum = (inv(awt) - inv(at)) * zs / (2 * math.tan(an))
    g1 = Gear(module, z1, pressure_angle, helix_angle)
    x1 = x_sum / 2 if not internal else 0.0
    if not internal and x1 < g1.x_min_undercut:
        x1 = g1.x_min_undercut
    x2 = (x_sum - x1) if not internal else (x_sum + x1)
    k = x_sum - (centre_distance - a0) / module if not internal else 0.0
    return {"x_sum": round(x_sum, 5), "x1": round(x1, 5), "x2": round(x2, 5),
            "tip_shortening": round(max(k, 0.0), 5),
            "alpha_wt_deg": round(math.degrees(awt), 5), "standard_centre_distance": round(a0, 4),
            "basis": "ISO 21771 inv(alpha_wt) relation; split: pinion undercut limit, else equal [neutral]"}


def mesh(g1: Gear, g2: Gear, face_width: Optional[float] = None,
         centre_distance: Optional[float] = None) -> Dict:
    """Pair check for g1 (pinion, external) with g2 (external or internal).

    Returns centre distance, working pressure angle, contact ratios, tip clearances,
    backlash, mesh phase for the part frames used by tooth_space() and warnings."""
    if g1.internal:
        raise ValueError("g1 must be the external pinion")
    w: List[str] = []
    if abs(g1.mn - g2.mn) > 1e-9 or abs(g1.pressure_angle - g2.pressure_angle) > 1e-9:
        w.append("module or pressure angle differ: the gears cannot mesh")
    if abs(g1.helix_angle - g2.helix_angle) > 1e-9:
        w.append("helix angles differ")
    if g1.beta:
        same = g1.hand == g2.hand
        if g2.internal and not same:
            w.append("internal helical pair needs the same hand")
        if not g2.internal and same:
            w.append("external helical pair needs opposite hands")
    awt = working_pressure_angle(g1, g2)
    zs = (g2.teeth - g1.teeth) if g2.internal else (g1.teeth + g2.teeth)
    a0 = zs * g1.mt / 2
    aw = a0 * math.cos(g1.alpha_t) / math.cos(awt)
    if centre_distance is not None:
        aw_used = float(centre_distance)
        cwa = a0 * math.cos(g1.alpha_t) / aw_used
        if not 0 < cwa < 1:
            raise ValueError("centre distance out of range")
        awt_used = math.acos(cwa)
    else:
        aw_used, awt_used = aw, awt
    ga1 = math.sqrt(max(g1.ra ** 2 - g1.rb ** 2, 0.0))
    ga2 = math.sqrt(max(g2.ra ** 2 - g2.rb ** 2, 0.0))
    if g2.internal:
        eps_a = (ga1 - ga2 + aw_used * math.sin(awt_used)) / g1.pbt
        clearance1 = g2.rf - (aw_used + g1.ra)                 # pinion tip to ring root
        clearance2 = g2.ra - (aw_used + g1.rf)                  # ring tip to pinion root
        if g2.teeth - g1.teeth < 10:
            w.append("z2 - z1 = %d < 10: tip (trochoid) interference likely [heur KHK]"
                     % (g2.teeth - g1.teeth))
        if g2.tip_clamped:
            w.append("ring tips were shortened to the base circle")
    else:
        eps_a = (ga1 + ga2 - aw_used * math.sin(awt_used)) / g1.pbt
        clearance1 = aw_used - g1.ra - g2.rf
        clearance2 = aw_used - g2.ra - g1.rf
        line = aw_used * math.sin(awt_used)
        if ga2 > line + 1e-9:
            w.append("involute interference: gear 2 tip reaches below the pinion base circle")
        if ga1 > line + 1e-9:
            w.append("involute interference: pinion tip reaches below the gear 2 base circle")
    eps_b = (face_width * math.sin(g1.beta) / (math.pi * g1.mn)) if (face_width and g1.beta) else 0.0
    if eps_a < 1.0:
        w.append("transverse contact ratio %.3f < 1: no continuous contact" % eps_a)
    elif eps_a < 1.2:
        w.append("transverse contact ratio %.3f < 1.2 [heur]" % eps_a)
    for c in (clearance1, clearance2):
        if c < 0:
            w.append("tip/root collision: clearance %.3f mm" % c)
        elif c < 0.1 * g1.mn:
            w.append("small tip clearance %.3f mm < 0.1 m" % c)
    for g in (g1, g2):
        w.extend("%s: %s" % ("pinion" if g is g1 else "gear 2", m) for m in g.checks())
    # backlash from tooth thinning plus any centre distance above the zero-backlash one
    jt = g1.thinning + g2.thinning
    if centre_distance is not None:
        jt += 2 * aw_used * (inv(awt_used) - inv(awt)) * (-1 if g2.internal else 1)
    # mesh phase (rotation about each part's own Z axis at the z = 0 face), gear 2 centre at +X
    if g2.internal:
        phase1 = (math.pi / g1.teeth) % (2 * math.pi / g1.teeth)
        phase2 = 0.0
    else:
        phase1 = 0.0
        phase2 = (math.pi - math.pi / g2.teeth) % (2 * math.pi / g2.teeth)
    ratio = g2.teeth / g1.teeth
    out = {
        "centre_distance": round(aw_used, 4),
        "zero_backlash_centre_distance": round(aw, 4),
        "standard_centre_distance": round(a0, 4),
        "alpha_wt_deg": round(math.degrees(awt_used), 4),
        "ratio": round(ratio, 6),
        "contact_ratio": round(eps_a, 4),
        "overlap_ratio": round(eps_b, 4) if g1.beta else None,
        "tip_clearance": [round(clearance1, 4), round(clearance2, 4)],
        "backlash_circumferential": round(jt, 4),
        "backlash_normal": round(jt * math.cos(g1.alpha_t) * math.cos(g1.beta), 4),
        "phase_deg": [round(math.degrees(phase1), 5), round(math.degrees(phase2), 5)],
        "layout": ("ring at origin, pinion centre at +X a_w" if g2.internal else
                   "pinion at origin, gear 2 centre at +X a_w") + "; rotate each part by phase_deg about Z",
        "warnings": w,
    }
    if g1.beta:
        out["axial_force_per_tangential"] = round(math.tan(g1.beta), 4)
    return out


# ----------------------------------------------------------------------------------------
# racks
# ----------------------------------------------------------------------------------------
def rack_profile(module: float, length_pitches: int, pressure_angle: float = 20.0,
                 helix_angle: float = 0.0, backlash: float = 0.0, profile: str = "A",
                 height: Optional[float] = None) -> Dict:
    """Transverse outline of a rack (basic rack tooth, ISO 53) as lines and arcs.

    The datum (pitch) line is y = 0, teeth point to +y, the rack starts and ends at a
    tooth-space centre (x = 0 and x = n p_t). height = datum line above the back face
    (default 9 m, as common catalogue racks [cat KHK SRS]).
    Returns {'segments': closed loop, 'pitch', 'length', 'datum_height', ...}."""
    ha, hf, rho_c = ISO53_PROFILES[profile.upper()]
    mn = module
    an, b = math.radians(pressure_angle), math.radians(helix_angle)
    cb = math.cos(b)
    p = math.pi * mn / cb                        # transverse pitch
    tan_t = math.tan(an) / cb                    # transverse flank slope (dx per dy)
    at = math.atan(tan_t)
    s_datum = math.pi * mn / 2 / cb - backlash / 2   # transverse tooth thickness at the datum
    h_d = 9.0 * mn if height is None else float(height)
    y_root, y_tip = -hf * mn, ha * mn
    # root fillet: circle tangent to the root line and the flank (transverse: radius rho
    # in the normal section becomes an ellipse; the circle of radius rho is used [heur])
    rho = rho_c * mn
    half_space_root = (p - s_datum) / 2 - hf * mn * tan_t      # half space width at the root line
    rho_max = half_space_root / (1 / math.cos(at) - math.tan(at))
    rho = min(rho, max(rho_max, 0.0))
    # build one period starting at the space centre (x = 0, root line), going +x
    def period(x0):
        out = []
        yc = y_root + rho                                 # fillet centre height
        # left flank of the next tooth: the space widens toward the tip
        def xf(y):
            return x0 + (p - s_datum) / 2 + y * tan_t
        cx = xf(yc) - rho / math.cos(at)
        a_start = -math.pi / 2
        a_end = -math.pi / 2 + (math.pi / 2 - at)
        t0 = (cx, y_root)
        t1 = (cx + rho * math.cos(a_end), yc + rho * math.sin(a_end))
        out.append({"type": "line", "points": [(x0, y_root), t0]})
        out.append({"type": "arc", "center": (cx, yc), "radius": rho, "a0": a_start, "a1": a_end})
        top_l = (xf(y_tip), y_tip)
        out.append({"type": "line", "points": [t1, top_l]})
        top_r = (x0 + p - (xf(y_tip) - x0), y_tip)
        out.append({"type": "line", "points": [top_l, top_r]})
        # right flank of the tooth, mirrored about the tooth centre x0 + p/2
        m = lambda q: (2 * (x0 + p / 2) - q[0], q[1])
        t1m, t0m = m(t1), m(t0)
        out.append({"type": "line", "points": [top_r, t1m]})
        out.append({"type": "arc", "center": m((cx, yc)), "radius": rho,
                    "a0": math.pi - a_end, "a1": math.pi - a_start})
        out.append({"type": "line", "points": [t0m, (x0 + p, y_root)]})
        return out
    n = int(length_pitches)
    chain = []
    for k in range(n):
        chain.extend(period(k * p))
    # merge consecutive root lines
    merged = []
    for s in chain:
        if merged and s["type"] == "line" and merged[-1]["type"] == "line" and \
                abs(s["points"][0][1] - y_root) < 1e-12 and abs(s["points"][1][1] - y_root) < 1e-12 and \
                abs(merged[-1]["points"][0][1] - y_root) < 1e-12 and abs(merged[-1]["points"][1][1] - y_root) < 1e-12:
            merged[-1] = {"type": "line", "points": [merged[-1]["points"][0], s["points"][1]]}
        else:
            merged.append(s)
    L = n * p
    back = -h_d
    loop = merged + [
        {"type": "line", "points": [(L, y_root), (L, back)]},
        {"type": "line", "points": [(L, back), (0.0, back)]},
        {"type": "line", "points": [(0.0, back), (0.0, y_root)]},
    ]
    for s in loop:
        if s["type"] == "arc":
            c, r = s["center"], s["radius"]
            s["start"] = (c[0] + r * math.cos(s["a0"]), c[1] + r * math.sin(s["a0"]))
            s["end"] = (c[0] + r * math.cos(s["a1"]), c[1] + r * math.sin(s["a1"]))
            s["ccw"] = s["a1"] > s["a0"]
    # tooth thickness check at the tip
    s_tip = s_datum - 2 * ha * mn * tan_t
    return {"segments": loop, "pitch": p, "length": L, "datum_height": h_d, "root_fillet": rho,
            "tip_land": s_tip, "transverse_pressure_angle_deg": math.degrees(at),
            "basis": "ISO 53 profile %s basic rack; datum height %s" %
                     (profile.upper(), "9 m [cat KHK SRS]" if height is None else "[req]")}


# ----------------------------------------------------------------------------------------
# planetary sets
# ----------------------------------------------------------------------------------------
def planetary(ratio: float, planets: int = 3, module: float = 1.0, z_min: int = 17,
              z_max: int = 150, sun: Optional[int] = None, planet: Optional[int] = None,
              results: int = 3) -> Dict:
    """Simple planetary set (ring fixed, sun in, carrier out, i = 1 + z_r / z_s) with equal
    modules and no profile shift: z_r = z_s + 2 z_p, (z_s + z_r) / N integer, neighbouring
    planets clear by at least 0.5 m, ring z_r - z_p >= 10 [heur KHK].
    Ranked by ratio error, then by the smallest ring [neutral: smallest envelope]."""
    N = int(planets)
    cands = []
    zs_range = [sun] if sun else range(z_min, z_max + 1)
    for zs in zs_range:
        zp_range = [planet] if planet else range(z_min, z_max + 1)
        for zp in zp_range:
            zr = zs + 2 * zp
            if zr > 3 * z_max:
                break
            if (zs + zr) % N:
                continue
            gap = (zs + zp) * math.sin(math.pi / N) - (zp + 2)        # in modules, tip to tip
            if gap < 0.5:
                continue
            if zr - zp < 10:
                continue
            i = 1 + zr / zs
            cands.append((abs(i - ratio), zr, zs, zp, i, gap))
    cands.sort()
    out = []
    for err, zr, zs, zp, i, gap in cands[:results]:
        ring = Gear(module, zr, internal=True)
        out.append({"sun": zs, "planet": zp, "ring": zr, "planets": N, "ratio": round(i, 5),
                    "ratio_error": round(i - ratio, 5), "centre_distance": round((zs + zp) * module / 2, 4),
                    "ring_root_diameter": round(ring.df, 3), "planet_gap": round(gap * module, 3),
                    "ring_tip_clamped": ring.tip_clamped,
                    "phases": planet_phases(zs, zp, zr, N)})
    return {"candidates": out, "basis": "concentric and equal-spacing assembly conditions; ring fixed, "
            "sun input, carrier output"}


def planet_phases(zs: int, zp: int, zr: int, N: int) -> Dict:
    """Rotation of each part about its own axis (deg) so that all meshes close, with the sun
    at 0 and planet k at carrier angle 360 k / N (parts in the tooth_space() frame)."""
    def wrap(a, period):                          # a mod period, with values within 1e-9 of the period -> 0
        v = a % period
        return 0.0 if min(v, period - v) < 1e-9 else v
    out = {"sun": 0.0, "ring": round(math.degrees(wrap(math.pi * zp / zr, 2 * math.pi / zr)), 6), "planets": []}
    for k in range(N):
        th = 2 * math.pi * k / N
        ph = wrap(th + math.pi - math.pi / zp + th * zs / zp, 2 * math.pi / zp)
        out["planets"].append({"carrier_angle": round(math.degrees(th), 6), "rotation": round(math.degrees(ph), 6)})
    return out


# ----------------------------------------------------------------------------------------
# worm gear sets
# ----------------------------------------------------------------------------------------
def worm_set(module: float, starts: int, wheel_teeth: int, diameter_quotient: Optional[float] = None,
             pressure_angle: float = 20.0, friction: float = 0.05) -> Dict:
    """Cylindrical worm (ZA, straight axial profile) and wheel geometry (DIN 3975 / ISO 14521
    relations). diameter_quotient q = d1 / m, default 10 [heur, DIN 3976 range 8-20]."""
    q = 10.0 if diameter_quotient is None else float(diameter_quotient)
    m = module
    d1 = q * m
    gamma = math.atan(starts / q)
    d2 = wheel_teeth * m
    a = (d1 + d2) / 2
    an = math.atan(math.tan(math.radians(pressure_angle)) * math.cos(gamma))
    phi = math.atan(friction / math.cos(an))
    eff = math.tan(gamma) / math.tan(gamma + phi)
    out = {
        "worm": {"d1": d1, "da1": d1 + 2 * m, "df1": d1 - 2.4 * m, "axial_pitch": math.pi * m,
                 "lead": starts * math.pi * m, "lead_angle_deg": round(math.degrees(gamma), 4),
                 "length_min": round(2 * math.sqrt((d2 / 2 + m) ** 2 - (d2 / 2 - m) ** 2) + math.pi * m, 3)},
        "wheel": {"d2": d2, "da2_throat": d2 + 2 * m, "df2": d2 - 2.4 * m,
                  "de2_max": d2 + 3 * m, "face_width": round(0.75 * (d1 + 2 * m), 3),
                  "helix_angle_deg": round(math.degrees(gamma), 4)},
        "centre_distance": a,
        "ratio": wheel_teeth / starts,
        "efficiency_worm_driving": round(eff, 4),
        "self_locking_static": gamma < phi,
        "basis": "DIN 3975 geometry, clearance 0.2 m [std], q [heur], face width 0.75 d_a1 [heur]",
    }
    return out
