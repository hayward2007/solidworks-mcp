"""Native SolidWorks gear features (late-bound COM, SolidWorks 2025).

Part frame of every cylindrical gear: axis = +Z through the origin, the z = 0 face on the
Front plane, one tooth space centred on +X at z = 0 (the frame of Gear.tooth_space()).
A reference axis "Gear axis" is added for mates. Racks: datum (pitch) line on the X axis,
teeth toward +Y, length along +X, face width along +Z.

Each builder checks its own result: rebuild errors, body count, and the volume against the
exact transverse area x face width (normally within 0.05 %). Helical builds also probe the
material once to confirm the hand.
"""
from __future__ import annotations

import math
import time
from typing import Dict, List, Optional

from .. import com
from . import geometry as geo
from . import bevel as bev

MM = 1e-3
SW_BODY_INTERSECT = 15901
_TWIST_SIGN = {"value": 1.0}       # SolidWorks twist direction vs. CCW about +Z (verified per build)

# DIN 6885-1 / KS B 1311 parallel keys: (bore over, bore up to, key width b, hub groove depth t2)
DIN6885 = ((6, 8, 2, 1.0), (8, 10, 3, 1.4), (10, 12, 4, 1.8), (12, 17, 5, 2.3), (17, 22, 6, 2.8),
           (22, 30, 8, 3.3), (30, 38, 10, 3.3), (38, 44, 12, 3.3), (44, 50, 14, 3.8), (50, 58, 16, 4.3),
           (58, 65, 18, 4.4), (65, 75, 20, 4.9), (75, 85, 22, 5.4), (85, 95, 25, 5.4), (95, 110, 28, 6.4))


def keyway_for_bore(d: float) -> Optional[Dict]:
    for lo, hi, b, t2 in DIN6885:
        if lo < d <= hi:
            return {"width": float(b), "depth": float(t2), "basis": "DIN 6885-1 hub groove"}
    return None


# ----------------------------------------------------------------------------------------
# small SolidWorks helpers
# ----------------------------------------------------------------------------------------
def new_part(sw):
    template = com.call(sw, "GetUserPreferenceStringValue", 8)          # swDefaultTemplatePart
    doc = com.call(sw, "NewDocument", template, 0, 0, 0)
    if doc is None:
        raise RuntimeError("could not create a part: check the default part template")
    return doc


def _plane(doc, which):
    return com.default_plane_name(doc, which)


def _last(doc, name=None):
    feat = com.call(doc, "FeatureByPositionReverse", 0)
    if feat is not None and name:
        try:
            feat.Name = name
        except Exception:
            pass
    return feat


def _select(feat, append=False, mark=0):
    if not com.call(feat, "Select2", append, mark):
        raise RuntimeError("cannot select %s" % feat.Name)


def draw_segments(sm, segments, dx=0.0, dy=0.0) -> int:
    """Sketch entities for geometry segments (mm) in the active 2D sketch."""
    made = 0
    for s in segments:
        if s["type"] == "arc":
            (cx, cy), (x0, y0), (x1, y1) = s["center"], s["start"], s["end"]
            e = com.call(sm, "CreateArc", (cx + dx) * MM, (cy + dy) * MM, 0.0, (x0 + dx) * MM, (y0 + dy) * MM,
                         0.0, (x1 + dx) * MM, (y1 + dy) * MM, 0.0, 1 if s["ccw"] else -1)
        elif s["type"] == "line":
            (x0, y0), (x1, y1) = s["points"][0], s["points"][-1]
            e = com.call(sm, "CreateLine", (x0 + dx) * MM, (y0 + dy) * MM, 0.0, (x1 + dx) * MM,
                         (y1 + dy) * MM, 0.0)
        else:
            flat = [v for (x, y) in s["points"] for v in ((x + dx) * MM, (y + dy) * MM, 0.0)]
            e = com.call(sm, "CreateSpline2", com.arr(flat), False)
        made += e is not None
    return made


def sketch(doc, plane_name, draw, name):
    """2D sketch on a plane; draw(sketch_manager) creates entities in mm via draw_segments.
    Entities go straight to the database (no snapping), so tiny teeth stay exact.
    Returns (sketch feature, number of closed contours)."""
    com.call(doc, "ClearSelection2", True)
    if not com.select(doc, plane_name, "PLANE"):
        raise RuntimeError("cannot select plane %s" % plane_name)
    sm = doc.SketchManager
    com.call(sm, "InsertSketch", True)
    sm.AddToDB = True
    try:
        draw(sm)
        sk = com.val(sm, "ActiveSketch")
        contours = com.val(sk, "GetSketchContours") if sk is not None else None
        n = len(contours) if contours else 0
    finally:
        sm.AddToDB = False
        com.call(sm, "InsertSketch", True)
    return _last(doc, name), n


def sketch3d_line(doc, p0, p1, name):
    sm = doc.SketchManager
    com.call(doc, "ClearSelection2", True)
    com.call(sm, "Insert3DSketch", True)
    sm.AddToDB = True
    try:
        com.call(sm, "CreateLine", p0[0] * MM, p0[1] * MM, p0[2] * MM, p1[0] * MM, p1[1] * MM, p1[2] * MM)
    finally:
        sm.AddToDB = False
        com.call(sm, "Insert3DSketch", True)
    return _last(doc, name)


def model_to_sketch(sw, sk, points_mm):
    """Sketch coordinates (metres) of model points (mm) for the sketch being edited."""
    mu = com.val(sw, "GetMathUtility")
    xf = com.val(sk, "ModelToSketchTransform")
    out = []
    for x, y, z in points_mm:
        pt = com.call(mu, "CreatePoint", com.arr([x * MM, y * MM, z * MM]))
        a = com.call(pt, "MultiplyTransform", xf).ArrayData
        out.append((a[0], a[1]))
    return out


def revolve(doc, sk, name):
    com.call(doc, "ClearSelection2", True)
    _select(sk)
    f = com.call(doc.FeatureManager, "FeatureRevolve2", True, True, False, False, False, False, 0, 0,
                 2 * math.pi, 0.0, False, False, 0.0, 0.0, 0, 0.0, 0.0, True, True, True)
    if f is None:
        raise RuntimeError("revolve failed (%s)" % name)
    f.Name = name
    return f


def sketch3d(doc, draw, name):
    """3D sketch in model coordinates (mm); draw(sm) creates the entities."""
    sm = doc.SketchManager
    com.call(doc, "ClearSelection2", True)
    com.call(sm, "Insert3DSketch", True)
    sm.AddToDB = True
    try:
        draw(sm)
    finally:
        sm.AddToDB = False
        com.call(sm, "Insert3DSketch", True)
    return _last(doc, name)


def _spline3d(sm, pts):
    return com.call(sm, "CreateSpline2", com.arr([c * MM for p in pts for c in p]), False)


def _line3d(sm, a, b):
    return com.call(sm, "CreateLine", a[0] * MM, a[1] * MM, a[2] * MM, b[0] * MM, b[1] * MM, b[2] * MM)


def extrude(doc, sk, depth, name):
    com.call(doc, "ClearSelection2", True)
    _select(sk)
    f = com.call(doc.FeatureManager, "FeatureExtrusion3", True, False, False, 0, 0, depth * MM, 0.0,
                 False, False, False, False, 0.0, 0.0, False, False, False, False, True, True, True,
                 0, 0.0, False)
    if f is None:
        raise RuntimeError("extrude failed (%s)" % name)
    f.Name = name
    return f


def cut_through(doc, sk, name):
    com.call(doc, "ClearSelection2", True)
    _select(sk)
    f = com.call(doc.FeatureManager, "FeatureCut4", False, False, False, 1, 1, 0.01, 0.01,
                 False, False, False, False, 0.0, 0.0, False, False, False, False,
                 False, True, True, False, False, False, 0, 0.0, False, False)
    if f is None:
        raise RuntimeError("cut failed (%s)" % name)
    f.Name = name
    return f


def sweep(doc, profile, path, twist, name, cut=True, twist_mode=8):
    """Sweep the profile sketch along the path sketch. twist_mode 8 = constant twist along the
    path (radians), 1 = keep normal constant (pure translation)."""
    com.call(doc, "ClearSelection2", True)
    _select(profile, False, 1)
    _select(path, True, 4)
    fm = doc.FeatureManager
    if cut:
        f = com.call(fm, "InsertCutSwept5", False, True, twist_mode, False, False, 0, 0, False, 0.0, 0.0, 0, 0,
                     True, True, float(twist), True, False, False, False, False, 0.0, 0)
    else:
        f = com.call(fm, "InsertProtrusionSwept4", False, True, twist_mode, False, False, 0, 0, False, 0.0, 0.0,
                     0, 0, True, True, True, float(twist), True, False, 0.0, 0)
    if f is None:
        raise RuntimeError("sweep failed (%s)" % name)
    f.Name = name
    return f


def z_axis(doc, name="Gear axis"):
    com.call(doc, "ClearSelection2", True)
    com.select(doc, _plane(doc, "top"), "PLANE")
    com.select(doc, _plane(doc, "right"), "PLANE", append=True)
    com.call(doc, "InsertAxis2", True)
    return _last(doc, name)


def circular_pattern(doc, axis, feat, n, name, geometry_pattern=True):
    com.call(doc, "ClearSelection2", True)
    _select(axis, False, 1)
    _select(feat, True, 4)
    f = com.call(doc.FeatureManager, "FeatureCircularPattern5", int(n), 2 * math.pi, False, "NULL",
                 bool(geometry_pattern), True, False, False, False, False, 1, 0.0, "NULL", False)
    if f is None:
        raise RuntimeError("circular pattern failed (%s)" % name)
    f.Name = name
    return f


def delete_feature(doc, feat):
    com.call(doc, "ClearSelection2", True)
    _select(feat)
    com.call(doc.Extension, "DeleteSelection2", 0)


def bodies(doc) -> List:
    out = com.call(doc, "GetBodies2", 0, True)
    return list(out) if out else []


def volume_mm3(doc) -> Optional[float]:
    mp = com.val(doc.Extension, "CreateMassProperty")
    return None if mp is None else float(mp.Volume) * 1e9


def material_fraction(sw, doc, x, y, z0, z1, radius) -> float:
    """Share of a small probe cylinder (axis Z, mm) that lies inside the part's material.
    Temporary bodies only: the model is not changed."""
    modeler = com.val(sw, "GetModeler")
    tool = com.call(modeler, "CreateBodyFromCyl", com.arr([x * MM, y * MM, z0 * MM, 0.0, 0.0, 1.0,
                                                          radius * MM, (z1 - z0) * MM]))
    v_tool = float(com.call(tool, "GetMassProperties", 1.0)[3])
    inside = 0.0
    for b in bodies(doc):
        res = com.call(com.val(b, "Copy"), "Operations2", SW_BODY_INTERSECT, com.val(tool, "Copy"), com.byref_int())
        for rb in (res or []):
            inside += float(com.call(rb, "GetMassProperties", 1.0)[3])
    return inside / v_tool if v_tool else 0.0


def _report(doc, t0, expected_volume, extra) -> Dict:
    from .. import verification
    rep = verification.model_report(doc)
    vol = volume_mm3(doc)
    out = {"document": rep.get("document"), "time_s": round(time.time() - t0, 2)}
    out.update(extra)
    out["volume_mm3"] = round(vol, 2) if vol else None
    if expected_volume:
        out["volume_expected_mm3"] = round(expected_volume, 2)
        out["volume_error_pct"] = round(100 * (vol - expected_volume) / expected_volume, 4) if vol else None
    out["bodies"] = len(bodies(doc))
    out["errors"] = rep.get("errors", [])
    out["box_mm"] = rep.get("box_mm")
    return out


# ----------------------------------------------------------------------------------------
# cylindrical gears
# ----------------------------------------------------------------------------------------
def build_cylindrical_gear(sw, gear: geo.Gear, face_width: float, bore: float = 0.0,
                           rim_diameter: Optional[float] = None, herringbone: bool = False,
                           keyway: bool = False, doc=None) -> Dict:
    """Spur, helical, herringbone or internal (ring) gear as native features:
    blank extrude -> one tooth-space cut (extrude, or sweep with constant twist) ->
    circular pattern -> (herringbone: mirror body about the mid face) -> (hub) -> (keyway).

    Helical gears are cut from a rim blank and get a separate "Hub" boss afterwards:
    SolidWorks 2025 drops the twist of a cut sweep whose path (the gear axis) runs inside
    the body, so the axis must lie in air while the teeth are cut (verified by probing)."""
    t0 = time.time()
    if face_width <= 0:
        raise ValueError("face_width must be > 0")
    doc = doc or new_part(sw)
    front = _plane(doc, "front")
    b = float(face_width)
    w = b / 2 if herringbone else b
    notes: List[str] = []
    if gear.internal:
        r_rim = (rim_diameter / 2) if rim_diameter else gear.rf + 3 * gear.mn
        if r_rim <= gear.rf + 0.5 * gear.mn:
            raise ValueError("rim_diameter too small for the root diameter %.3f" % gear.df)
        radii = [gear.ra, r_rim]
        bore = 0.0
    else:
        if bore and bore / 2 >= gear.rf - 0.5 * gear.mn:
            raise ValueError("bore too large for the root diameter %.3f" % gear.df)
        radii = [gear.ra] + ([bore / 2] if bore else [])
    hub_r = 0.0
    if gear.beta and not gear.internal and not bore:
        hub_r = 0.5 * gear.rf                    # construction bore, filled by the hub later
        radii = [gear.ra, hub_r]
    blank_sk, _ = sketch(doc, front, lambda sm: [com.call(sm, "CreateCircleByRadius", 0.0, 0.0, 0.0, r * MM)
                                                 for r in radii], "Blank sketch")
    extrude(doc, blank_sk, w, "Gear blank")
    axis = z_axis(doc)
    loop = gear.tooth_space()
    space_sk, contours = sketch(doc, front, lambda sm: draw_segments(sm, loop["segments"]), "Tooth space sketch")
    if contours != 1:
        notes.append("tooth space sketch has %d contours (expected 1)" % contours)
    if gear.beta == 0:
        space = cut_through(doc, space_sk, "Tooth space")
    else:
        path = sketch3d_line(doc, (0, 0, 0), (0, 0, w), "Helix path")
        space = sweep(doc, space_sk, path, _TWIST_SIGN["value"] * gear.twist(w), "Tooth space")
        ok = _check_hand(sw, doc, gear, w)
        if ok is False:                        # twisted the wrong way: flip once and remember
            delete_feature(doc, space)
            _TWIST_SIGN["value"] *= -1
            space = sweep(doc, space_sk, path, _TWIST_SIGN["value"] * gear.twist(w), "Tooth space")
            ok = _check_hand(sw, doc, gear, w)
        if not ok:
            notes.append("helix twist not confirmed by probing: check the teeth visually")
    circular_pattern(doc, axis, space, gear.teeth, "Teeth")
    if herringbone:
        _mirror_about_end_face(doc, gear, bore if not hub_r else 2 * hub_r, w)
    if hub_r:
        h_sk, _ = sketch(doc, front, lambda sm: com.call(sm, "CreateCircleByRadius", 0.0, 0.0, 0.0,
                                                        hub_r * MM), "Hub sketch")
        extrude(doc, h_sk, b, "Hub")
    key = None
    if keyway and bore and not gear.internal:
        key = keyway_for_bore(bore)
        if key:
            r_b, kw, t2 = bore / 2, key["width"], key["depth"]
            x_end = r_b + t2
            k_sk, _ = sketch(doc, front, lambda sm: com.call(sm, "CreateCornerRectangle", 0.0, -kw / 2 * MM, 0.0,
                                                             x_end * MM, kw / 2 * MM, 0.0), "Keyway sketch")
            cut_through(doc, k_sk, "Keyway")
        else:
            notes.append("no DIN 6885 key for bore %.1f mm" % bore)
    area = gear.transverse_area(bore=bore, rim_diameter=(2 * radii[1]) if gear.internal else None)
    expected = area * b
    if key:
        # keyway area outside the bore circle: rectangle minus the bore segment
        r_b, kw, t2 = bore / 2, key["width"], key["depth"]
        half = math.asin(min(kw / 2 / r_b, 1.0))
        seg = r_b ** 2 * (half - math.sin(half) * math.cos(half))          # circular segment beyond the chord
        chord_x = r_b * math.cos(half)
        expected -= ((r_b + t2 - chord_x) * kw - seg) * b
    extra = {"gear": gear.summary(), "face_width": b, "bore": bore or None,
             "checks": gear.checks() + notes}
    if gear.internal:
        extra["rim_diameter"] = round(2 * radii[1], 3)
    if herringbone:
        extra["herringbone"] = True
    if key:
        extra["keyway"] = key
    return _report(doc, t0, expected, extra)


def _check_hand(sw, doc, gear: geo.Gear, w: float) -> Optional[bool]:
    """Probe the tooth space near the axial position where the helix has turned a quarter
    pitch: material should be absent at the predicted angle and present on the other side."""
    quarter = (math.pi / gear.teeth) / 2
    rot_full = abs(gear.twist(w))
    z = w * min(1.0, quarter / rot_full) if rot_full > 0 else w
    z = min(max(z, 0.2 * w), 0.9 * w)
    th = gear.twist(z)
    r = gear.r
    rad = 0.12 * gear.mn
    h = 0.05 * gear.mn
    pred = material_fraction(sw, doc, r * math.cos(th), r * math.sin(th), z - h, z + h, rad)
    other = material_fraction(sw, doc, r * math.cos(-th), r * math.sin(-th), z - h, z + h, rad)
    if pred < 0.05 and other > 0.5:
        return True
    if other < 0.05 and pred > 0.5:
        return False
    return None


def _mirror_about_end_face(doc, gear: geo.Gear, bore: float, w: float):
    """Herringbone: mirror the helical half about its end face (z = w) and merge."""
    if gear.internal:
        r_pick = gear.rf + 1.0 * gear.mn
    else:
        r_pick = 0.5 * (gear.rf + (bore / 2 if bore else 0.0))
    com.call(doc, "ClearSelection2", True)
    if not com.select(doc, "", "FACE", False, 2, r_pick * MM, 0.0, w * MM):
        raise RuntimeError("cannot pick the end face for the herringbone mirror")
    for bd in bodies(doc):
        com.select(doc, bd.Name, "SOLIDBODY", True, 256)
    f = com.call(doc.FeatureManager, "InsertMirrorFeature2", True, False, True, False, 0)
    if f is None:
        raise RuntimeError("herringbone mirror failed")
    f.Name = "Herringbone mirror"
    return f


# ----------------------------------------------------------------------------------------
# racks
# ----------------------------------------------------------------------------------------
def build_rack(sw, module: float, pitches: int, face_width: float, pressure_angle: float = 20.0,
               helix_angle: float = 0.0, hand: str = "right", backlash: float = 0.0,
               height: Optional[float] = None, profile: str = "A", doc=None) -> Dict:
    """Rack with ISO 53 teeth. Datum line on X, teeth toward +Y, starts and ends at a tooth
    space centre. Helical racks are swept along a slanted line and trimmed square.
    A rack meshes with a pinion of the opposite hand."""
    t0 = time.time()
    doc = doc or new_part(sw)
    front = _plane(doc, "front")
    b = float(face_width)
    beta = math.radians(abs(helix_angle))
    base = geo.rack_profile(module, pitches, pressure_angle, abs(helix_angle), backlash, profile, height)
    p, L = base["pitch"], base["length"]
    expected = abs(geo.polygon_area(geo.loop_points(base, 16))) * b
    notes: List[str] = []
    if beta == 0:
        sk, n = sketch(doc, front, lambda sm: draw_segments(sm, base["segments"]), "Rack sketch")
        extrude(doc, sk, b, "Rack")
    else:
        # right hand: profile moves -x along +z (teeth toward +y); left hand: +x
        shift = (-1.0 if not str(hand).lower().startswith("l") else 1.0) * math.tan(beta) * b
        extra = int(math.ceil(abs(shift) / p)) + 1
        ext = geo.rack_profile(module, pitches + 2 * extra, pressure_angle, abs(helix_angle), backlash,
                               profile, height)
        sk, n = sketch(doc, front, lambda sm: draw_segments(sm, ext["segments"], dx=-extra * p), "Rack sketch")
        # SolidWorks starts a sweep at the path end nearer the profile: start the (translation
        # only) path at the middle of the profile so it runs toward +Z
        xm, ym = (-extra * p + ext["length"] - extra * p) / 2, -base["datum_height"] / 2
        path = sketch3d_line(doc, (xm, ym, 0), (xm + shift, ym, b), "Rack helix path")
        sweep(doc, sk, path, 0.0, "Rack", cut=False, twist_mode=1)
        y_lo, y_hi = -base["datum_height"] - 1.0, 2.0 * module + 1.0
        big = abs(shift) + (extra + 2) * p

        def trim(sm):
            com.call(sm, "CreateCornerRectangle", -big * MM, y_lo * MM, 0.0, 0.0, y_hi * MM, 0.0)
            com.call(sm, "CreateCornerRectangle", L * MM, y_lo * MM, 0.0, (L + big) * MM, y_hi * MM, 0.0)
        tk, _ = sketch(doc, front, trim, "Rack trim sketch")
        cut_through(doc, tk, "Rack ends")
    if n != 1:
        notes.append("rack sketch has %d contours (expected 1)" % n)
    extra_info = {"rack": {"module": module, "pitches": pitches, "pitch": round(p, 5), "length": round(L, 4),
                           "face_width": b, "datum_height": base["datum_height"],
                           "helix_angle": abs(helix_angle), "hand": hand if beta else None,
                           "tip_land": round(base["tip_land"], 4), "basis": base["basis"]},
                  "mesh_note": "pinion centre at (k p, r + x m) above the datum line, rotated by "
                               "-90 - 180/z deg (a tooth pointing -Y); opposite hand for helical",
                  "checks": notes}
    return _report(doc, t0, expected, extra_info)


# ----------------------------------------------------------------------------------------
# mesh check with temporary bodies (no assembly needed)
# ----------------------------------------------------------------------------------------
def _xform(sw, angle, tx=0.0, ty=0.0, tz=0.0):
    c, s = math.cos(angle), math.sin(angle)
    mu = com.val(sw, "GetMathUtility")
    return com.call(mu, "CreateTransform", com.arr([c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0,
                                                    tx * MM, ty * MM, tz * MM, 1.0, 0.0, 0.0, 0.0]))


def _posed(sw, body, angle, tx=0.0, ty=0.0):
    cp = com.val(body, "Copy")
    com.call(cp, "ApplyTransform", _xform(sw, angle, tx, ty))
    return cp


def mesh_check(sw, doc1, doc2, z1: int, z2: int, centre_distance: float, phase1_deg: float = 0.0,
               phase2_deg: float = 0.0, kind: str = "external", pitch_radius1: float = 0.0,
               rack_offset: float = 0.0, steps: int = 6) -> Dict:
    """Interference volume between two gear parts rolled through one pitch of the pinion.

    kind 'external': pinion (doc1) at the origin, gear (doc2) at (+a, 0).
    kind 'internal': ring (doc2) at the origin, pinion (doc1) at (+a, 0).
    kind 'rack':     pinion at the origin, rack datum line at y = -rack_offset (r + x m).
    Phases are the part rotations about their own Z axes from geometry.mesh() / the rack note.
    Returns the largest interference (mm3) and the per-step values."""
    b1, b2 = bodies(doc1), bodies(doc2)
    if not b1 or not b2:
        raise RuntimeError("both documents need a solid body")
    b1, b2 = b1[0], b2[0]
    p1, p2 = math.radians(phase1_deg), math.radians(phase2_deg)
    vols, errors = [], []
    for k in range(steps):
        th = (2 * math.pi / z1) * k / steps
        if kind == "external":
            t1 = _posed(sw, b1, p1 + th)
            t2 = _posed(sw, b2, p2 - th * z1 / z2, centre_distance, 0.0)
        elif kind == "internal":
            t1 = _posed(sw, b1, p1 + th, centre_distance, 0.0)
            t2 = _posed(sw, b2, p2 + th * z1 / z2)
        else:
            t1 = _posed(sw, b1, p1 + th)
            t2 = _posed(sw, b2, 0.0, pitch_radius1 * th, -rack_offset)
        err = com.byref_int()
        res = com.call(t1, "Operations2", SW_BODY_INTERSECT, t2, err)
        if err.value not in (0, 1):            # 1 = swBodyOperationNoIntersect (empty result)
            errors.append(int(err.value))
        v = sum(float(com.call(rb, "GetMassProperties", 1.0)[3]) for rb in (res or [])) * 1e9
        vols.append(round(v, 4))
    out = {"max_interference_mm3": max(vols), "per_step_mm3": vols, "kind": kind,
           "rolled_deg": round(360.0 / z1, 4)}
    if errors:
        out["boolean_errors"] = errors
    return out


# ----------------------------------------------------------------------------------------
# bevel gears
# ----------------------------------------------------------------------------------------
def build_bevel_gear(sw, gear: "bev.BevelGear", bore: float = 0.0, keyway: bool = False, doc=None) -> Dict:
    """Straight or spiral bevel gear: revolved blank (apex at the origin, axis +Z) -> one
    tooth space as a loft cut through Tredgold sections with 4 guide curves -> circular
    pattern -> bore (and DIN 6885 keyway)."""
    t0 = time.time()
    doc = doc or new_part(sw)
    notes: List[str] = []
    prof = gear.blank_profile(bore)
    top = _plane(doc, "top")
    z_lo, z_hi = prof[0][1] - 1.0, prof[-1][1] + 1.0

    def draw_blank(sm):
        sk = com.val(sm, "ActiveSketch")
        pts = model_to_sketch(sw, sk, [(r, 0.0, z) for r, z in prof])
        for a, b in zip(pts, pts[1:] + pts[:1]):
            com.call(sm, "CreateLine", a[0], a[1], 0.0, b[0], b[1], 0.0)
        ax = model_to_sketch(sw, sk, [(0.0, 0.0, z_lo), (0.0, 0.0, z_hi)])
        com.call(sm, "CreateCenterLine", ax[0][0], ax[0][1], 0.0, ax[1][0], ax[1][1], 0.0)
    bsk, n = sketch(doc, top, draw_blank, "Blank sketch")
    revolve(doc, bsk, "Gear blank")
    axis = z_axis(doc)
    sections = [gear.section(R) for R in gear.section_radii()]
    feats = []
    for i, sec in enumerate(sections):
        def draw(sm, sec=sec):
            _spline3d(sm, sec["right"])
            _line3d(sm, sec["right"][-1], sec["left"][0])
            _spline3d(sm, sec["left"])
            _line3d(sm, sec["left"][-1], sec["right"][0])
        feats.append(sketch3d(doc, draw, "Tooth section %d" % (i + 1)))
    guides = []
    for c in range(4):
        pts = [sec["corners"][c] for sec in sections]
        guides.append(sketch3d(doc, lambda sm, pts=pts: (_spline3d(sm, pts) if len(pts) > 2
                                                         else _line3d(sm, pts[0], pts[1])),
                               "Tooth guide %d" % (c + 1)))
    com.call(doc, "ClearSelection2", True)
    for f in feats:
        _select(f, True, 1)
    for f in guides:
        _select(f, True, 2)
    cut = com.call(doc.FeatureManager, "InsertCutBlend", False, False, False, 1.0, 0, 0, False, 0.0, 0.0, 0,
                   True, True)
    if cut is None:
        raise RuntimeError("tooth space loft failed")
    cut.Name = "Tooth space"
    circular_pattern(doc, axis, cut, gear.z, "Teeth")
    key = None
    if bore:                                   # the bore is part of the revolved blank
        front = _plane(doc, "front")
        if keyway:
            key = keyway_for_bore(bore)
            if key:
                kw, x_end = key["width"], bore / 2 + key["depth"]
                k_sk, _ = sketch(doc, front, lambda sm: com.call(sm, "CreateCornerRectangle", 0.0, -kw / 2 * MM,
                                                                 0.0, x_end * MM, kw / 2 * MM, 0.0), "Keyway sketch")
                cut_through(doc, k_sk, "Keyway")
    extra = {"gear": gear.summary(), "checks": gear.checks() + notes, "bore": bore or None}
    if key:
        extra["keyway"] = key
    return _report(doc, t0, None, extra)


def _xform_rows(sw, rows, t=(0.0, 0.0, 0.0)):
    mu = com.val(sw, "GetMathUtility")
    return com.call(mu, "CreateTransform", com.arr(list(rows) + [t[0] * MM, t[1] * MM, t[2] * MM,
                                                                1.0, 0.0, 0.0, 0.0]))


def bevel_mesh_check(sw, doc1, doc2, z1: int, z2: int, phase2_deg: float, steps: int = 6) -> Dict:
    """Interference of a 90 deg bevel pair (apexes at the part origins): gear 1 axis +Z,
    gear 2 axis +X (its part X -> world -Z), rolled through one pinion pitch."""
    b1, b2 = bodies(doc1)[0], bodies(doc2)[0]
    p2 = math.radians(phase2_deg)
    vols, errors = [], []
    for k in range(steps):
        th = (2 * math.pi / z1) * k / steps
        t1 = _posed(sw, b1, th)
        a = p2 - th * z1 / z2
        c, s = math.cos(a), math.sin(a)
        rows = (0.0, s, -c,  0.0, c, s,  1.0, 0.0, 0.0)
        t2 = com.val(b2, "Copy")
        com.call(t2, "ApplyTransform", _xform_rows(sw, rows))
        err = com.byref_int()
        res = com.call(t1, "Operations2", SW_BODY_INTERSECT, t2, err)
        if err.value not in (0, 1):
            errors.append(int(err.value))
        vols.append(round(sum(float(com.call(rb, "GetMassProperties", 1.0)[3]) for rb in (res or [])) * 1e9, 4))
    out = {"max_interference_mm3": max(vols), "per_step_mm3": vols, "kind": "bevel",
           "rolled_deg": round(360.0 / z1, 4)}
    if errors:
        out["boolean_errors"] = errors
    return out


# ----------------------------------------------------------------------------------------
# worm gear sets (ZA worm: straight axial profile)
# ----------------------------------------------------------------------------------------
def worm_axial_space(module: float, starts: int, q: float, pressure_angle: float = 20.0,
                     backlash: float = 0.0, ext: Optional[float] = None) -> Dict:
    """Axial section of one thread space (radius rho, axial z), centred on z = 0."""
    m = module
    r1 = q * m / 2
    gamma = math.atan(starts / q)
    alpha_x = math.atan(math.tan(math.radians(pressure_angle)) / math.cos(gamma))
    ra, rf = r1 + m, r1 - 1.2 * m                 # h_a = m, clearance 0.2 m [std DIN 3975]
    e = math.pi * m / 2 + backlash / 2            # axial space width at the reference cylinder
    ext = 0.5 * m if ext is None else ext
    top = ra + ext
    hw = lambda rho: e / 2 + (rho - r1) * math.tan(alpha_x)
    if hw(rf) <= 0:
        raise ValueError("thread space closes at the root: lower the pressure angle or module")
    poly = [(rf, -hw(rf)), (top, -hw(top)), (top, hw(top)), (rf, hw(rf))]
    # first moment of the part of the space inside the tip cylinder about the axis (for volumes)
    def moment(lo, hi, n=400):
        s = 0.0
        for i in range(n):
            rho = lo + (hi - lo) * (i + 0.5) / n
            s += rho * 2 * hw(rho) * (hi - lo) / n
        return s
    return {"r1": r1, "ra": ra, "rf": rf, "gamma": gamma, "alpha_x": alpha_x, "lead": starts * math.pi * m,
            "axial_pitch": math.pi * m, "polygon": poly, "moment_inside": moment(rf, ra)}


def build_worm(sw, module: float, starts: int = 1, length: Optional[float] = None,
               diameter_quotient: float = 10.0, pressure_angle: float = 20.0, hand: str = "right",
               backlash: float = 0.0, bore: float = 0.0, doc=None) -> Dict:
    """Cylindrical ZA worm, axis +Z from z = 0 to the length: the axial thread space is swept
    along a helix (3D spline through the exact helix) and patterned for multi-start worms."""
    t0 = time.time()
    doc = doc or new_part(sw)
    ws = worm_axial_space(module, starts, diameter_quotient, pressure_angle, backlash)
    L = float(length) if length else round(geo.worm_set(module, starts, 40, diameter_quotient)["worm"]["length_min"], 1)
    lead, r1 = ws["lead"], ws["r1"]
    front, top = _plane(doc, "front"), _plane(doc, "top")
    radii = [ws["ra"]] + ([bore / 2] if bore else [])
    bsk, _ = sketch(doc, front, lambda sm: [com.call(sm, "CreateCircleByRadius", 0.0, 0.0, 0.0, r * MM)
                                            for r in radii], "Blank sketch")
    extrude(doc, bsk, L, "Worm blank")
    axis = z_axis(doc, "Worm axis")
    z0 = -0.75 * lead
    z_end = L + 0.75 * lead
    sign = 1.0 if not str(hand).lower().startswith("l") else -1.0

    def draw_profile(sm):
        sk = com.val(sm, "ActiveSketch")
        pts = model_to_sketch(sw, sk, [(rho, 0.0, z0 + z) for rho, z in ws["polygon"]])
        for a, b in zip(pts, pts[1:] + pts[:1]):
            com.call(sm, "CreateLine", a[0], a[1], 0.0, b[0], b[1], 0.0)
    psk, n = sketch(doc, top, draw_profile, "Thread space sketch")
    turns = (z_end - z0) / lead
    npts = int(math.ceil(turns * 24)) + 1
    helix = [(r1 * math.cos(sign * 2 * math.pi * turns * i / (npts - 1)),
              r1 * math.sin(sign * 2 * math.pi * turns * i / (npts - 1)),
              z0 + (z_end - z0) * i / (npts - 1)) for i in range(npts)]
    path = sketch3d(doc, lambda sm: _spline3d(sm, helix), "Helix path")
    cut = sweep(doc, psk, path, 0.0, "Thread space", cut=True, twist_mode=0)
    if starts > 1:
        circular_pattern(doc, axis, cut, starts, "Threads")
    vol_expected = math.pi * (ws["ra"] ** 2 - (bore / 2) ** 2) * L - (L / ws["axial_pitch"]) * 2 * math.pi * ws["moment_inside"]
    extra = {"worm": {"module": module, "starts": starts, "q": diameter_quotient, "d1": round(2 * r1, 4),
                      "da1": round(2 * ws["ra"], 4), "df1": round(2 * ws["rf"], 4), "lead": round(lead, 4),
                      "lead_angle_deg": round(math.degrees(ws["gamma"]), 4),
                      "axial_pressure_angle_deg": round(math.degrees(ws["alpha_x"]), 4), "hand": hand,
                      "length": L, "basis": "ZA worm, DIN 3975 proportions (h_a = m, c = 0.2 m)"},
             "checks": [] if n == 1 else ["thread profile sketch has %d contours" % n]}
    return _report(doc, t0, vol_expected, extra)


def build_worm_wheel(sw, module: float, teeth: int, starts: int = 1, diameter_quotient: float = 10.0,
                     pressure_angle: float = 20.0, hand: str = "right", face_width: Optional[float] = None,
                     backlash: float = 0.0, bore: float = 0.0, throat: bool = True, doc=None) -> Dict:
    """Worm wheel approximated as a helical gear (helix angle = worm lead angle, same hand,
    normal module m cos(gamma)) with a toroidal throat around the worm [heur: involute
    helical wheel, point contact; for hobbed line contact use the gear maker's data]."""
    ws = geo.worm_set(module, starts, teeth, diameter_quotient, pressure_angle)
    gamma = math.radians(ws["worm"]["lead_angle_deg"])
    mn = module * math.cos(gamma)
    b2 = float(face_width) if face_width else ws["wheel"]["face_width"]
    k = 1 - 1.5 / math.cos(gamma)                        # outside diameter d2 + 3 m [heur DIN 3975]
    k_throat = 1 - 1.0 / math.cos(gamma)                  # tip at the throat diameter d2 + 2 m
    g = geo.Gear(mn, teeth, pressure_angle, math.degrees(gamma), hand, 0.0, backlash, tip_shortening=k)
    for _ in range(40):                                   # keep rim tips >= 0.3 m thick [heur]
        if g.tip_thickness >= 0.3 * mn or k >= k_throat:
            break
        k = min(k + 0.02, k_throat)
        g = geo.Gear(mn, teeth, pressure_angle, math.degrees(gamma), hand, 0.0, backlash, tip_shortening=k)
    rep = build_cylindrical_gear(sw, g, b2, bore=bore, doc=doc)
    doc = doc or sw.ActiveDoc
    if throat:
        a = ws["centre_distance"]
        r_t = module * diameter_quotient / 2 - module      # worm root + clearance seen from the wheel
        top = _plane(doc, "top")

        def draw(sm):
            sk = com.val(sm, "ActiveSketch")
            c, p = model_to_sketch(sw, sk, [(a, 0.0, b2 / 2), (a + r_t, 0.0, b2 / 2)])
            com.call(sm, "CreateCircle", c[0], c[1], 0.0, p[0], p[1], 0.0)
            ax = model_to_sketch(sw, sk, [(0.0, 0.0, -1.0), (0.0, 0.0, b2 + 1.0)])
            com.call(sm, "CreateCenterLine", ax[0][0], ax[0][1], 0.0, ax[1][0], ax[1][1], 0.0)
        tsk, _ = sketch(doc, top, draw, "Throat sketch")
        com.call(doc, "ClearSelection2", True)
        _select(tsk)
        f = com.call(doc.FeatureManager, "FeatureRevolve2", True, True, False, True, False, False, 0, 0,
                     2 * math.pi, 0.0, False, False, 0.0, 0.0, 0, 0.0, 0.0, True, True, True)
        if f is None:
            rep.setdefault("checks", []).append("throat cut failed")
        else:
            f.Name = "Throat"
        vol = volume_mm3(doc)
        rep["volume_mm3"] = round(vol, 2) if vol else None
        rep.pop("volume_expected_mm3", None)
        rep.pop("volume_error_pct", None)
        rep["throat_radius"] = round(r_t, 4)
    rep["worm_set"] = ws
    return rep
