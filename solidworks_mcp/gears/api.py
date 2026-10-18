"""Argument handling for the gear MCP tools (gear_design, create_gear).

Defaults carry their basis so the agent can report them:
- pressure angle 20 deg [std ISO 53], profile A [std ISO 53]
- backlash 0.04 m for the mesh [heur: machined gears 0.03-0.08 mm at m 1, 0.05-0.12 at m 2]
- face width 10 m (cylindrical) [heur KHK, Shigley 3p-5p]; bevel min(R_e/3, 10 m) [heur AGMA]
- profile shift x = 0, or the undercut limit x_min when z is small [std ISO 21771 / DIN 3960]
- internal-gear rim diameter d_f + 6 m [heur ISO 6336-3 backup ratio >= 1.2]
- mating gear: opposite hand (external), same hand (internal) [std]
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional

from . import bevel as bev
from . import geometry as geo

CYLINDRICAL = ("spur", "helical", "herringbone", "internal", "ring")


def _f(a: Dict, key: str, default=None):
    v = a.get(key, default)
    return default if v is None else v


def _teeth(a: Dict) -> List[int]:
    t = a.get("teeth")
    if t is None:
        raise ValueError("teeth is required")
    if isinstance(t, (list, tuple)):
        return [int(v) for v in t]
    out = [int(t)]
    if a.get("mate_teeth"):
        out.append(int(a["mate_teeth"]))
    return out


def _backlash(a: Dict, m: float):
    if a.get("backlash") is not None:
        return float(a["backlash"]), "[req]"
    return round(0.04 * m, 3), "[heur] 0.04 m"


def _shifts(a: Dict, zs: List[int], m: float, alpha: float, beta: float, internal_mate: bool):
    """Profile shifts: given, from a centre distance, or the undercut limit for small pinions."""
    xs = a.get("profile_shift")
    if xs is not None:
        xs = list(xs) if isinstance(xs, (list, tuple)) else [float(xs)]
        while len(xs) < len(zs):
            xs.append(0.0)
        return [float(v) for v in xs], None, "[req]"
    if a.get("centre_distance") and len(zs) == 2:
        s = geo.shift_for_centre_distance(m, zs[0], zs[1], float(a["centre_distance"]), alpha, beta, internal_mate)
        return [s["x1"], s["x2"]], s, "[calc] ISO 21771 for the centre distance"
    def up(v):                                   # round up so x >= x_min survives rounding
        return math.ceil(max(0.0, v) * 1e4) / 1e4
    x1 = up(geo.Gear(m, zs[0], alpha, beta).x_min_undercut)
    out = [x1]
    basis = "[std] undercut limit x_min" if x1 else "[neutral] x = 0"
    if len(zs) == 2:
        if internal_mate:
            out.append(x1)                       # equal shifts keep the internal centre distance
        else:
            xmin2 = geo.Gear(m, zs[1], alpha, beta).x_min_undercut
            if x1 and -x1 >= xmin2 + 0.05:
                out.append(-x1)
                basis += "; V-zero pair (x2 = -x1) keeps the standard centre distance"
            else:
                x2 = up(xmin2)
                out.append(x2)
                if x2:
                    basis = "[std] undercut limit x_min on both gears"
    return out, None, basis


def design(a: Dict) -> Dict:
    """gear_design: dimensions and checks, no CAD."""
    kind = str(a.get("kind", "pair")).lower()
    m = float(a["module"]) if a.get("module") is not None else None
    alpha = float(_f(a, "pressure_angle", 20.0))
    if kind == "planetary":
        return geo.planetary(float(a["ratio"]), int(_f(a, "planets", 3)), m or 1.0,
                             sun=a.get("sun"), planet=a.get("planet"))
    if m is None:
        raise ValueError("module is required")
    if kind == "worm":
        return geo.worm_set(m, int(_f(a, "starts", 1)), int(_teeth(a)[0]), a.get("diameter_quotient"), alpha)
    if kind == "rack":
        return {k: v for k, v in geo.rack_profile(m, int(_f(a, "pitches", 10)), alpha, float(_f(a, "helix_angle", 0)),
                                                  _backlash(a, m)[0]).items() if k != "segments"}
    if kind == "bevel":
        zs = _teeth(a)
        if len(zs) < 2:
            raise ValueError("bevel needs teeth [z1, z2] (or teeth + mate_teeth)")
        sp = float(_f(a, "spiral_angle", 0.0))
        hand = _f(a, "hand", "right")
        bl = _backlash(a, m)[0]
        g1 = bev.BevelGear(m, zs[0], zs[1], float(_f(a, "shaft_angle", 90)), a.get("face_width"), alpha, sp,
                           a.get("cutter_radius"), hand, _f(a, "system", "gleason"), backlash=bl)
        g2 = bev.BevelGear(m, zs[1], zs[0], float(_f(a, "shaft_angle", 90)), a.get("face_width"), alpha, sp,
                           a.get("cutter_radius") or g1.r_c,
                           "left" if str(hand).lower().startswith("r") else "right", _f(a, "system", "gleason"),
                           backlash=bl)
        return {"gear1": g1.summary(), "gear2": g2.summary(), "mesh": bev.bevel_mesh(g1, g2),
                "checks": g1.checks() + g2.checks()}
    # cylindrical gear or pair
    zs = _teeth(a)
    beta = float(_f(a, "helix_angle", 0.0))
    internal = bool(a.get("internal")) or kind in ("internal", "ring")
    xs, shift_info, x_basis = _shifts(a, zs, m, alpha, beta, internal and len(zs) == 2)
    bl, bl_basis = _backlash(a, m)
    hand = _f(a, "hand", "right")
    b = float(_f(a, "face_width", 10 * m))
    g1 = geo.Gear(m, zs[0], alpha, beta, hand, xs[0], bl, internal and len(zs) == 1)
    out = {"gear1": g1.summary(), "basis": {"profile_shift": x_basis, "backlash": bl_basis,
                                            "face_width": "[req]" if a.get("face_width") else "[heur] 10 m"}}
    if shift_info:
        out["shift"] = shift_info
    if len(zs) == 2:
        mate_hand = hand if internal else ("left" if str(hand).lower().startswith("r") else "right")
        k = shift_info["tip_shortening"] if shift_info else 0.0
        g1 = geo.Gear(m, zs[0], alpha, beta, hand, xs[0], bl, False, k)
        g2 = geo.Gear(m, zs[1], alpha, beta, mate_hand, xs[1], bl, internal, k)
        out["gear1"], out["gear2"] = g1.summary(), g2.summary()
        out["mesh"] = geo.mesh(g1, g2, b, a.get("centre_distance"))
    else:
        out["checks"] = g1.checks()
    out["face_width"] = b
    return out


def _save(sw, doc, path: Optional[str], suffix: str = "") -> Optional[str]:
    if not path:
        return None
    from .. import com
    p = path
    if os.path.isdir(p) or p.endswith(("\\", "/")):
        os.makedirs(p, exist_ok=True)
        p = os.path.join(p, "gear%s.SLDPRT" % suffix)
    elif suffix:
        root, ext = os.path.splitext(p)
        p = root + suffix + (ext or ".SLDPRT")
    if not p.lower().endswith(".sldprt"):
        p += ".SLDPRT"
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    error = com.call(doc, "SaveAs3", p, 0, 1)                    # silent save (the part takes the name)
    return p if error == 0 and os.path.exists(p) else None


def create(sw, a: Dict) -> Dict:
    """create_gear: build the part(s) in SolidWorks and check them."""
    from . import build
    typ = str(a.get("type", "spur")).lower().replace("-", "_").replace(" ", "_")
    m = float(a["module"])
    alpha = float(_f(a, "pressure_angle", 20.0))
    bl, bl_basis = _backlash(a, m)
    hand = _f(a, "hand", "right")
    bore = float(_f(a, "bore", 0.0))
    keyway = bool(a.get("keyway", False))
    save = a.get("save_path")
    pair = bool(a.get("build_mate", False))
    if typ == "rack":
        rep = build.build_rack(sw, m, int(_f(a, "pitches", 10)), float(_f(a, "face_width", 10 * m)), alpha,
                               float(_f(a, "helix_angle", 0.0)), hand, bl, a.get("height"))
        rep["saved"] = _save(sw, sw.ActiveDoc, save)
        return rep
    if typ in ("worm", "worm_set", "worm_wheel"):
        starts = int(_f(a, "starts", 1))
        q = float(_f(a, "diameter_quotient", 10.0))
        out = {}
        if typ in ("worm", "worm_set"):
            out["worm"] = build.build_worm(sw, m, starts, a.get("length"), q, alpha, hand, bl, bore)
            out["worm"]["saved"] = _save(sw, sw.ActiveDoc, save, "_worm" if typ == "worm_set" else "")
        if typ in ("worm_wheel", "worm_set"):
            z2 = int(_teeth(a)[-1] if a.get("teeth") is not None else a["wheel_teeth"])
            out["wheel"] = build.build_worm_wheel(sw, m, z2, starts, q, alpha, hand, a.get("face_width"), bl,
                                                  float(_f(a, "wheel_bore", bore if typ == "worm_wheel" else 0.0)))
            out["wheel"]["saved"] = _save(sw, sw.ActiveDoc, save, "_wheel" if typ == "worm_set" else "")
        out["note"] = ("wheel = involute helical gear with throat [heur]; same hand as the worm; mesh found "
                       "zero interference with backlash >= 0.05 m at the right phase in tests")
        return out if len(out) > 2 else next(v for k, v in out.items() if k != "note")
    if typ in ("bevel", "straight_bevel", "spiral_bevel"):
        zs = _teeth(a)
        if len(zs) < 2:
            raise ValueError("bevel gears need mate_teeth (pitch angle depends on the ratio)")
        sp = float(_f(a, "spiral_angle", 35.0 if typ == "spiral_bevel" else 0.0))
        g1 = bev.BevelGear(m, zs[0], zs[1], float(_f(a, "shaft_angle", 90)), a.get("face_width"), alpha, sp,
                           a.get("cutter_radius"), hand, _f(a, "system", "gleason"), backlash=bl)
        r1 = build.build_bevel_gear(sw, g1, bore, keyway)
        d1 = sw.ActiveDoc
        r1["saved"] = _save(sw, d1, save, "_1" if pair else "")
        if not pair:
            r1["basis"] = {"backlash": bl_basis}
            return r1
        g2 = bev.BevelGear(m, zs[1], zs[0], float(_f(a, "shaft_angle", 90)), a.get("face_width"), alpha, sp,
                           a.get("cutter_radius") or g1.r_c,
                           "left" if str(hand).lower().startswith("r") else "right", _f(a, "system", "gleason"),
                           backlash=bl)
        r2 = build.build_bevel_gear(sw, g2, float(_f(a, "mate_bore", bore)), keyway)
        d2 = sw.ActiveDoc
        r2["saved"] = _save(sw, d2, save, "_2")
        mesh = bev.bevel_mesh(g1, g2)
        check = build.bevel_mesh_check(sw, d1, d2, zs[0], zs[1], mesh["phase_deg"][1]) \
            if abs(g1.shaft_angle - 90) < 1e-9 else {"note": "mesh check needs a 90 deg shaft angle"}
        return {"gear1": r1, "gear2": r2, "mesh": mesh, "mesh_check": check}
    if typ not in CYLINDRICAL:
        raise ValueError("type must be spur, helical, herringbone, internal, rack, bevel, spiral_bevel, worm, "
                         "worm_wheel or worm_set")
    zs = _teeth(a)
    beta = float(_f(a, "helix_angle", 20.0 if typ in ("helical", "herringbone") else 0.0))
    internal = typ in ("internal", "ring")
    if internal and pair:
        raise ValueError("for a ring gear with its pinion build the pinion with mate_teeth and internal_mate=true")
    internal_mate = bool(a.get("internal_mate", False))
    xs, shift_info, x_basis = _shifts(a, zs, m, alpha, beta, internal_mate)
    k = shift_info["tip_shortening"] if shift_info else 0.0
    b = float(_f(a, "face_width", 10 * m))
    herring = typ == "herringbone"
    g1 = geo.Gear(m, zs[0], alpha, beta, hand, xs[0], bl, internal, k)
    rim = a.get("rim_diameter") or (g1.df + 6 * m if internal else None)
    r1 = build.build_cylindrical_gear(sw, g1, b, bore, rim, herring, keyway)
    d1 = sw.ActiveDoc
    r1["basis"] = {"profile_shift": x_basis, "backlash": bl_basis,
                   "face_width": "[req]" if a.get("face_width") else "[heur] 10 m"}
    r1["saved"] = _save(sw, d1, save, "_1" if pair else "")
    if not (pair and len(zs) == 2):
        return r1
    mate_hand = hand if internal_mate else ("left" if str(hand).lower().startswith("r") else "right")
    g2 = geo.Gear(m, zs[1], alpha, beta, mate_hand, xs[1], bl, internal_mate, k)
    rim2 = a.get("mate_rim_diameter") or (g2.df + 6 * m if internal_mate else None)
    r2 = build.build_cylindrical_gear(sw, g2, b, float(_f(a, "mate_bore", 0.0 if internal_mate else bore)), rim2,
                                      herring, keyway and not internal_mate)
    d2 = sw.ActiveDoc
    r2["saved"] = _save(sw, d2, save, "_2")
    mesh = geo.mesh(g1, g2, b, a.get("centre_distance"))
    check = build.mesh_check(sw, d1, d2, zs[0], zs[1], mesh["centre_distance"], *mesh["phase_deg"],
                             kind="internal" if internal_mate else "external")
    if shift_info:
        mesh["shift"] = shift_info
    return {"gear1": r1, "gear2": r2, "mesh": mesh, "mesh_check": check}
