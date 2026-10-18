"""Topology results -> SolidWorks parts: 2D loops as an extruded plate, 3D STL import."""
from __future__ import annotations

import json
import math
import os
import time
from typing import Dict, List

from .. import com
from ..gears import build as gb

MM = 1e-3


def _pieces(loop, spacing: float, corner_deg: float = 35.0):
    """Split a closed loop at sharp corners into open runs resampled every ~spacing mm,
    so each run can be a spline without overshoot (corners stay sharp, G0)."""
    n = len(loop)
    turn = []
    for i in range(n):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        ang = abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
        turn.append(math.degrees(ang))
    corners = [i for i in range(n) if turn[i] > corner_deg]
    if not corners:                                   # smooth loop: start anywhere, close at the start
        corners = [0]
    runs = []
    for k, ci in enumerate(corners):
        cj = corners[(k + 1) % len(corners)]
        idx = list(range(ci, cj + 1)) if cj > ci else list(range(ci, n)) + list(range(0, cj + 1))
        run = [loop[i] for i in idx]
        runs.append(_resample(run, spacing))
    return runs


def _resample(run, spacing):
    L = [0.0]
    for a, b in zip(run, run[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = L[-1]
    m = max(1, int(round(total / spacing)))
    out, j = [], 0
    for k in range(m + 1):
        t = total * k / m
        while j < len(L) - 2 and L[j + 1] < t:
            j += 1
        seg = L[j + 1] - L[j] or 1.0
        f = (t - L[j]) / seg
        a, b = run[j], run[j + 1]
        out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
    out[0], out[-1] = tuple(run[0]), tuple(run[-1])  # exact shared corner points
    return out


def build_plate(sw, loops: List[List[List[float]]], thickness: float, spacing: float = 1.0, doc=None) -> Dict:
    """Closed loops (mm, outer CCW, holes CW) on the Front plane, extruded along +Z. Each loop is
    split at sharp corners into splines through points every ~spacing mm (lines for short runs)."""
    t0 = time.time()
    doc = doc or gb.new_part(sw)
    front = gb._plane(doc, "front")
    n_ent = [0]

    def draw(sm):
        for loop in loops:
            for run in _pieces([tuple(p) for p in loop], spacing):
                if len(run) >= 4:
                    flat = [v for (x, y) in run for v in (x * MM, y * MM, 0.0)]
                    com.call(sm, "CreateSpline2", com.arr(flat), False)
                else:
                    for a, b in zip(run, run[1:]):
                        com.call(sm, "CreateLine", a[0] * MM, a[1] * MM, 0.0, b[0] * MM, b[1] * MM, 0.0)
                n_ent[0] += 1
    sk, contours = gb.sketch(doc, front, draw, "Topology sketch")
    gb.extrude(doc, sk, thickness, "Topology plate")
    from .export import loops_area
    expected = loops_area(loops) * thickness
    vol = gb.volume_mm3(doc)
    return {"document": doc.GetTitle, "contours": contours, "loops": len(loops), "sketch_entities": n_ent[0],
            "thickness": thickness, "volume_mm3": round(vol, 2) if vol else None,
            "volume_expected_mm3": round(expected, 2),
            "volume_error_pct": round(100 * (vol - expected) / expected, 3) if vol and expected else None,
            "bodies": len(gb.bodies(doc)), "time_s": round(time.time() - t0, 2),
            "note": "smoothed iso-density 0.5 contour; add bolt holes and fillets as features"}


def import_stl(sw, path: str) -> Dict:
    """Open an STL as a solid (mesh) body part; units mm."""
    t0 = time.time()
    old_type = com.call(sw, "GetUserPreferenceIntegerValue", 208)       # swImportStlVrmlModelType
    old_units = com.call(sw, "GetUserPreferenceIntegerValue", 210)      # swImportStlVrmlUnits
    old_mesh = com.call(sw, "GetUserPreferenceToggle", 679)             # swVrmlStlImportAsPSMesh
    try:
        com.call(sw, "SetUserPreferenceIntegerValue", 208, 2)           # solid body
        com.call(sw, "SetUserPreferenceIntegerValue", 210, 0)           # mm
        com.call(sw, "SetUserPreferenceToggle", 679, True)              # as a (mesh BREP) solid, not surfaces
        err = com.byref_int()
        data = com.call(sw, "GetImportFileData", os.path.abspath(path))
        doc = com.call(sw, "LoadFile4", os.path.abspath(path), "r", data if data is not None else com.NOCALL, err)
    finally:
        com.call(sw, "SetUserPreferenceIntegerValue", 208, old_type)
        com.call(sw, "SetUserPreferenceIntegerValue", 210, old_units)
        com.call(sw, "SetUserPreferenceToggle", 679, bool(old_mesh))
    if doc is None:
        return {"success": False, "error_code": int(err.value), "file": path}
    vol = gb.volume_mm3(doc)
    return {"success": True, "document": doc.GetTitle, "volume_mm3": round(vol, 2) if vol else None,
            "bodies": len(gb.bodies(doc)), "time_s": round(time.time() - t0, 2),
            "note": "mesh solid body: use as reference geometry and remodel the load paths with features"}
