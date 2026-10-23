"""
Verification tools for the text-to-CAD loop
-------------------------------------------
model_report        compact numbers to check after every modeling step
render_views        small labelled grid of standard views (restores the user's view)
export_model        STEP / STL / 3MF / IGES / Parasolid / ... via Save As copy
check_interference  interference volumes between assembly components

Lengths are mm, volumes mm3, areas mm2, mass kg.
"""

import io
import math
import os
import re
import tempfile
from collections import Counter

from .com import byref_bool, call, features, val
from .precision import FEATURE_ERROR_LIMIT, LENGTH_DECIMALS, MASS_DECIMALS

DOC_TYPES = {1: "part", 2: "assembly", 3: "drawing"}
LENGTH_UNITS = {0: "mm", 1: "cm", 2: "m", 3: "inch", 4: "ft", 5: "ft-in", 8: "micron"}
VIEW_IDS = {"front": 1, "back": 2, "left": 3, "right": 4, "top": 5, "bottom": 6,
            "iso": 7, "isometric": 7, "trimetric": 8, "dimetric": 9}
# axes, planes, origins, temporary axes, coordinate systems, curves, sketches
_REFERENCE_TOGGLES = (4, 5, 6, 7, 13, 195, 196)
# feature-tree folders and default items that say nothing about the design
_TREE_NOISE = {
    "CommentsFolder", "FavoriteFolder", "HistoryFolder", "SelectionSetFolder", "SensorFolder",
    "DocsFolder", "DetailCabinet", "SurfaceBodyFolder", "SolidBodyFolder", "EnvFolder",
    "InkMarkupFolder", "EqnFolder", "MaterialFolder", "OriginProfileFeature", "MateGroup",
    "FtrFolder", "HistoryFolder", "BlockFolder", "LiveSectionFolder", "MarkupCommentFolder",
}
EXPORT_FORMATS = {
    "step": ".step", "stp": ".step", "iges": ".igs", "igs": ".igs", "stl": ".stl", "3mf": ".3mf",
    "parasolid": ".x_t", "x_t": ".x_t", "x_b": ".x_b", "sat": ".sat", "pdf": ".pdf", "dxf": ".dxf",
    "dwg": ".dwg", "png": ".png", "jpg": ".jpg", "edrawings": ".eprt",
}
RENDER_DIR = os.path.join(tempfile.gettempdir(), "solidworks_mcp", "renders")


def _mm(values):
    return [round(v * 1000.0, LENGTH_DECIMALS) for v in values]


def _box(six):
    lo, hi = _mm(six[:3]), _mm(six[3:6])
    return {"min": lo, "max": hi, "size": [round(b - a, LENGTH_DECIMALS) for a, b in zip(lo, hi)]}


def feature_errors(doc, limit=FEATURE_ERROR_LIMIT, tree=None):
    """Features (or mates) that fail to rebuild: [{feature, type, code, warning}]."""
    try:                                   # one call answers the common case: nothing is wrong
        if not val(doc.Extension, "GetWhatsWrongCount"):
            return []
    except Exception:
        pass
    found = []
    for feat in (tree if tree is not None else features(doc)):
        items = [feat]
        if val(feat, "GetTypeName2") == "MateGroup":
            items, sub = [], val(feat, "GetFirstSubFeature")
            while sub is not None:
                items.append(sub)
                sub = val(sub, "GetNextSubFeature")
        for item in items:
            try:
                warning = byref_bool(False)
                code = call(item, "GetErrorCode2", warning)
            except Exception:
                continue
            if code:
                found.append({"feature": item.Name, "type": val(item, "GetTypeName2"),
                              "code": int(code), "warning": bool(warning.value)})
                if len(found) >= limit:
                    return found
    return found


def mass_properties(mp):
    """Mass block of an IMassProperty (mm3, mm2, kg, kg/m3, mm).

    Mass and Density are read first: once Volume or SurfaceArea has been read, SolidWorks 2025
    returns them as if the density were 1 kg/m3 (an AISI 1020 part then reports 1/7900 of its mass).
    """
    mass, density = mp.Mass, mp.Density
    return {
        "volume_mm3": round(mp.Volume * 1e9, MASS_DECIMALS["volume_mm3"]),
        "area_mm2": round(mp.SurfaceArea * 1e6, MASS_DECIMALS["area_mm2"]),
        "mass_kg": round(mass, MASS_DECIMALS["mass_kg"]),
        "density_kg_m3": round(density, 1),
        "center_mm": _mm(mp.CenterOfMass),
    }


def model_report(doc, last=8):
    """Compact summary of the active document for the agent to check after each step."""
    if doc is None:
        return {"document": None, "note": "no active document"}
    kind = DOC_TYPES.get(val(doc, "GetType"), "other")
    report = {
        "document": val(doc, "GetTitle"),
        "type": kind,
        "path": val(doc, "GetPathName") or None,
        "unsaved_changes": bool(val(doc, "GetSaveFlag")),
        "units": LENGTH_UNITS.get(doc.LengthUnit, str(doc.LengthUnit)),
    }
    try:
        report["editing_sketch"] = val(doc.SketchManager, "ActiveSketch") is not None
    except Exception:
        pass

    tree = features(doc)
    design, default_planes = [], 0
    for feat in tree:
        kind_name = val(feat, "GetTypeName2")
        if kind_name in _TREE_NOISE:
            continue
        if kind_name == "RefPlane" and default_planes < 3:      # skip the three default planes
            default_planes += 1
            continue
        design.append((feat.Name, kind_name))
    report["features"] = {
        "count": len(design),
        "by_type": dict(Counter(t for _, t in design)),
        "last": [f"{n} ({t})" for n, t in design[-last:]],
    }
    report["errors"] = feature_errors(doc, tree=tree)

    if kind == "part":
        bodies = call(doc, "GetBodies2", 0, True) or ()          # visible solid bodies
        report["bodies"] = []
        for body in bodies[:8]:
            entry = {"name": body.Name, "faces": val(body, "GetFaceCount"), "edges": val(body, "GetEdgeCount")}
            if 1 < len(bodies) <= 4:                              # per-body volume only for small multibody parts
                entry["volume_mm3"] = round(call(body, "GetMassProperties", 1.0)[3] * 1e9, 2)
            report["bodies"].append(entry)
        if len(bodies) > 8:
            report["bodies_total"] = len(bodies)
        if bodies:
            report["box_mm"] = _box(call(doc, "GetPartBox", True))
        material = (val(doc, "MaterialIdName") or "").split("|")
        report["material"] = material[1] if len(material) > 1 and material[1] else None
    elif kind == "assembly":
        everything = call(doc, "GetComponents", False) or ()
        top = call(doc, "GetComponents", True) or ()
        report["components"] = {
            "top_level": len(top), "total": len(everything),
            "suppressed": sum(1 for c in everything if val(c, "IsSuppressed")),
            "names": [c.Name2 for c in top][:20],
        }
        mates = 0
        for feat in features(doc):
            if val(feat, "GetTypeName2") == "MateGroup":
                sub = val(feat, "GetFirstSubFeature")
                while sub is not None:
                    mates += 1
                    sub = val(sub, "GetNextSubFeature")
        report["mates"] = mates
        try:
            report["box_mm"] = _box(call(doc, "GetBox", 0))
        except Exception:
            pass

    if kind in ("part", "assembly"):
        try:
            report["mass"] = mass_properties(val(doc.Extension, "CreateMassProperty"))
        except Exception as exc:
            report["mass"] = {"error": str(exc)[:120]}
    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _crop_to_content(image, threshold=28, margin=0.04):
    """Crop away the (gradient) background, estimated from the left and right image edges."""
    from PIL import Image, ImageChops
    w, h = image.size
    left = image.crop((0, 0, 1, h)).resize((w, h))
    right = image.crop((w - 1, 0, w, h)).resize((w, h))
    ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h))   # 0 at left -> 255 at right
    background = Image.composite(right, left, ramp)
    mask = ImageChops.difference(image, background).convert("L").point(lambda v: 255 if v > threshold else 0)
    box = mask.getbbox()
    if not box:
        return image
    pad = int(max(box[2] - box[0], box[3] - box[1]) * margin) + 2
    return image.crop((max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, w), min(box[3] + pad, h)))


def _compose(items, size):
    from PIL import Image, ImageDraw
    tiles = []
    for label, path in items:
        picture = _crop_to_content(Image.open(path).convert("RGB"))
        picture.thumbnail((size, size), Image.LANCZOS)
        tile = Image.new("RGB", (size, size), "white")
        tile.paste(picture, ((size - picture.width) // 2, (size - picture.height) // 2))
        ImageDraw.Draw(tile).text((6, 4), label, fill=(70, 70, 70))
        tiles.append(tile)
    cols = 1 if len(tiles) == 1 else 2
    rows = math.ceil(len(tiles) / cols)
    grid = Image.new("RGB", (cols * size, rows * size), "white")
    draw = ImageDraw.Draw(grid)
    for i, tile in enumerate(tiles):
        grid.paste(tile, ((i % cols) * size, (i // cols) * size))
    for c in range(1, cols):
        draw.line([(c * size, 0), (c * size, rows * size)], fill=(210, 210, 210))
    for r in range(1, rows):
        draw.line([(0, r * size), (cols * size, r * size)], fill=(210, 210, 210))
    buffer = io.BytesIO()
    grid.save(buffer, "PNG", optimize=True)
    return buffer.getvalue(), grid.size


def render_views(doc, views=("iso", "front", "top", "right"), size=384, hide_references=True, app=None):
    """Save standard views as PNG, return one small labelled grid image.

    The user's view orientation, zoom and reference-geometry visibility are restored afterwards.
    Token cost of the returned image is about width * height / 750 (2x2 at 384 px ~ 790 tokens).
    PNG export captures the active window, so doc must be the active document.
    """
    if doc is None:
        return {"success": False, "message": "no active document"}
    if app is not None:
        current = val(app, "ActiveDoc")
        if current is None or val(current, "GetTitle") != val(doc, "GetTitle"):
            return {"success": False, "message": "render_views captures the active window: activate this document first"}
    os.makedirs(RENDER_DIR, exist_ok=True)
    stem = re.sub(r"[^\w.-]+", "_", val(doc, "GetTitle")) or "model"
    ext = doc.Extension
    view = val(doc, "ActiveView")
    saved_view = None
    if view is not None:
        try:
            saved_view = (view.Orientation3, view.Scale2, view.Translation3)
        except Exception:
            saved_view = None
    toggles = {}
    if hide_references:
        for toggle in _REFERENCE_TOGGLES:
            try:
                toggles[toggle] = bool(call(ext, "GetUserPreferenceToggle", toggle, 0))
                call(ext, "SetUserPreferenceToggle", toggle, 0, False)
            except Exception:
                pass
    saved, failed = [], []
    try:
        for name in views:
            view_id = VIEW_IDS.get(str(name).lower())
            if view_id is None:
                failed.append(f"{name}: unknown view")
                continue
            call(doc, "ShowNamedView2", "", view_id)
            val(doc, "ViewZoomtofit2")
            path = os.path.join(RENDER_DIR, f"{stem}_{name}.png")
            error = call(doc, "SaveAs3", path, 0, 3)          # silent + copy
            if error == 0 and os.path.exists(path):
                saved.append((name, path))
            else:
                failed.append(f"{name}: save error {error}")
    finally:
        for toggle, state in toggles.items():
            try:
                call(ext, "SetUserPreferenceToggle", toggle, 0, state)
            except Exception:
                pass
        if view is not None and saved_view is not None:
            try:
                view.Orientation3, view.Scale2, view.Translation3 = saved_view
                call(view, "GraphicsRedraw", None)
            except Exception:
                pass
    result = {"success": bool(saved), "views": [n for n, _ in saved], "files": [p for _, p in saved],
              "failed": failed}
    if saved:
        try:
            png, (w, h) = _compose(saved, int(size))
            result.update(image_png=png, width=w, height=h, approx_tokens=int(w * h / 750))
        except ImportError:
            result["note"] = "Pillow not installed: returning file paths only"
    return result


# ---------------------------------------------------------------------------
# Export and interference
# ---------------------------------------------------------------------------

def export_model(doc, fmt="step", path=None):
    """Save a copy of the active document in another format."""
    if doc is None:
        return {"success": False, "message": "no active document"}
    suffix = EXPORT_FORMATS.get(str(fmt).lower().lstrip("."))
    if path and not suffix:
        suffix = os.path.splitext(path)[1]
    if not suffix:
        return {"success": False, "message": f"unknown format {fmt}; use one of {sorted(EXPORT_FORMATS)}"}
    if not path:
        source = val(doc, "GetPathName")
        base = os.path.splitext(source)[0] if source else os.path.join(
            tempfile.gettempdir(), "solidworks_mcp", re.sub(r"[^\w.-]+", "_", val(doc, "GetTitle")))
        path = base + suffix
    elif not os.path.splitext(path)[1]:
        path += suffix
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    error = call(doc, "SaveAs3", path, 0, 3)                      # silent + copy
    ok = error == 0 and os.path.exists(path)
    return {"success": ok, "file": path, "error_code": int(error),
            "size_kb": round(os.path.getsize(path) / 1024, 1) if ok else None}


def check_interference(doc, limit=20):
    """Interference volumes between components of the active assembly."""
    if doc is None or val(doc, "GetType") != 2:
        return {"success": False, "message": "the active document is not an assembly"}
    manager = val(doc, "InterferenceDetectionManager")
    if manager is None:                    # e.g. an assembly opened invisibly (DocumentVisible False)
        return {"success": False, "message": "interference detection unavailable: make the assembly the active, visible document"}
    manager.TreatCoincidenceAsInterference = False
    manager.TreatSubAssembliesAsComponents = False
    manager.IncludeMultibodyPartInterferences = False
    manager.IgnoreHiddenBodies = True
    items = []
    try:
        for found in val(manager, "GetInterferences") or ():
            components = val(found, "Components") or ()
            items.append({"components": [c.Name2 for c in components],
                          "volume_mm3": round(val(found, "Volume") * 1e9, 3)})
    finally:
        val(manager, "Done")
    items.sort(key=lambda i: -i["volume_mm3"])
    return {"success": True, "count": len(items),
            "total_volume_mm3": round(sum(i["volume_mm3"] for i in items), 3), "items": items[:limit]}
