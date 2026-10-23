"""Read-only geometry observations; never infer original feature intent."""
import math
import re
import struct
from collections import Counter
from pathlib import Path
from .common import digest, finite, now
from ..precision import FEATURE_ERROR_LIMIT, LENGTH_DECIMALS, MASS_DECIMALS

# Numerical uncertainty attached to capture metrics, in each metric's own unit. It bounds how well a
# number represents the CAD model; density assignment, unmodeled parts and manufacturing are excluded.
LINEAR_PRECISION_MM = 1e-5      # Parasolid default linear precision (1e-8 m)
# Mass-property floors measured on SOLIDWORKS 2025 (design-evidence): analytic faces bounded by lines/circles
# matched closed forms within 5e-16; a pin with a cross hole (intersection edges) deviated 4.8e-6 in volume
# and 1.8e-5 in one face area, so every other model gets 1e-4.
REL_EXACT = 1e-8
REL_APPROXIMATE = 1e-4
ANALYTIC_SURFACES = ("IsPlane", "IsCylinder", "IsCone", "IsSphere", "IsTorus")
EXACT_CURVES = ("IsLine", "IsCircle", "IsEllipse")
MAX_CLASSIFIED_ENTITIES = 8000  # faces + edges; beyond this the model is treated as approximate
STL_EXTENT_BASIS = ("difference of the file's own vertex coordinates (float64 arithmetic on the stored values); "
                    "describes the mesh file, not the design intent or a physical part")


def inspect_stl(path, unit, max_triangles=1_000_000):
    if unit not in {"mm", "m", "inch"}:
        raise ValueError("STL is unitless: explicitly choose mm, m or inch")
    path = Path(path).expanduser().resolve()
    data = path.read_bytes()
    if len(data) > 256_000_000:
        raise ValueError("STL exceeds 256 MB inspection limit")
    scale = {"mm": 1.0, "m": 1000.0, "inch": 25.4}[unit]
    triangles = []
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else 0
    if count and len(data) == 84 + 50 * count:
        if count > max_triangles:
            raise ValueError("STL triangle limit exceeded")
        for i in range(count):
            values = struct.unpack_from("<12fH", data, 84 + 50 * i)
            triangles.append([tuple(scale * v for v in values[a:a + 3]) for a in (3, 6, 9)])
        fmt = "binary"
    else:
        try:
            text = data.decode("ascii")
            # Match complete vertex lines; malformed/extra coordinates are rejected.
            vertices = []
            for line in text.splitlines():
                fields = line.split()
                if fields and fields[0].lower() == "vertex":
                    if len(fields) != 4:
                        raise ValueError("malformed STL vertex")
                    vertices.append(tuple(scale * float(x) for x in fields[1:]))
            if not text.lstrip().lower().startswith("solid") or not vertices or len(vertices) % 3:
                raise ValueError("invalid ASCII STL")
            if len(vertices) // 3 > max_triangles:
                raise ValueError("STL triangle limit exceeded")
            triangles = [vertices[i:i + 3] for i in range(0, len(vertices), 3)]
        except (UnicodeDecodeError, OverflowError) as exc:
            raise ValueError("invalid or truncated STL") from exc
        fmt = "ascii"
    if not triangles:
        raise ValueError("empty STL")
    low, high = [math.inf] * 3, [-math.inf] * 3
    edges, oriented = Counter(), Counter()
    volume, area, degenerate = 0.0, 0.0, 0
    for tri in triangles:
        for v in tri:
            for axis, x in enumerate(v):
                finite(x, "STL coordinate")
                low[axis], high[axis] = min(low[axis], x), max(high[axis], x)
        a, b, c = tri
        ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0])
        face_area = math.sqrt(sum(v * v for v in cross)) / 2
        area += face_area
        degenerate += int(face_area == 0)
        volume += sum(a[i] * cross[i] for i in range(3)) / 6
        for u, v in ((a, b), (b, c), (c, a)):
            edges[tuple(sorted((u, v)))] += 1
            oriented[(u, v)] += 1
    manifold = all(v == 2 for v in edges.values()) and not degenerate
    consistent = manifold and all(oriented[(u, v)] == oriented[(v, u)] for u, v in oriented)
    reliable_volume = abs(volume) if consistent else None
    return {"capture_type": "stl-mesh", "captured": now(), "source_sha256": digest(data),
            "input_unit": unit, "format": fmt, "triangles": len(triangles), "box_mm": {"min": low, "max": high, "size": [high[i] - low[i] for i in range(3)]},
            "surface_area_mm2": area, "volume_mm3": reliable_volume, "closed_edge_manifold": manifold,
            "consistent_winding": consistent, "boundary_edges": sum(v == 1 for v in edges.values()),
            "nonmanifold_edges": sum(v > 2 for v in edges.values()), "degenerate_triangles": degenerate,
            "metrics": {"extent_" + axis: _metric(high[i] - low[i], "mm", 0.0, STL_EXTENT_BASIS)
                        for i, axis in enumerate("xyz")},
            "limitations": ["Exact coincident-vertex edge test; no welding tolerance is applied.",
                            "Closed edges/winding do not prove no self-intersections or overlapping/disconnected shells; volume is provisional.",
                            "Mesh geometry does not recover original dimensions, tolerances, materials, design intent or native feature history."]}


def _metric(value, unit, uncertainty, basis):
    """Evidence metric: uncertainty is in the metric's unit; None means it cannot satisfy a check."""
    return {"value": value, "unit": unit, "uncertainty": uncertainty, "uncertainty_basis": basis}


def _solid_bodies(doc, kind, val, call, issues):
    """(owner, body, transform array or None) for visible part bodies or unsuppressed component bodies."""
    if kind == "part":
        return [(body.Name, body, None) for body in call(doc, "GetBodies2", 0, True) or ()]
    items = []
    for comp in call(doc, "GetComponents", False) or ():
        if val(comp, "IsSuppressed"):
            continue
        bodies = call(comp, "GetBodies2", 0) or ()
        if not bodies:
            model = val(comp, "GetModelDoc2")
            if model is None or val(model, "GetType") != 2:      # subassembly nodes own no bodies themselves
                issues.append(f"{comp.Name2}: no resolved solid bodies (lightweight, empty or surface-only)")
            continue
        transform = None
        try:
            transform = call(comp, "GetTotalTransform", True)
        except Exception:
            transform = None
        if transform is None:
            transform = val(comp, "Transform2")
        array = list(transform.ArrayData)
        items.extend((comp.Name2, body, array) for body in bodies)
    return items


def _exact_extents(items, call, byref_double):
    """Tight axis-aligned extents (mm) in the document frame from IBody2.GetExtremePoint."""
    if not items:
        raise ValueError("no solid bodies")
    low, high = [math.inf] * 3, [-math.inf] * 3
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for owner, body, array in items:
        # Transform rows are the images of the part axes: p_doc = scale * sum(p_i * row_i) + shift.
        rows = identity if array is None else (array[0:3], array[3:6], array[6:9])
        shift = (0.0, 0.0, 0.0) if array is None else array[9:12]
        scale = 1.0 if array is None or not array[12] else array[12]
        for axis in range(3):
            for sign in (1.0, -1.0):
                direction = [sign * rows[i][axis] for i in range(3)]      # document axis seen from the part
                x, y, z = byref_double(), byref_double(), byref_double()
                if not call(body, "GetExtremePoint", direction[0], direction[1], direction[2], x, y, z):
                    raise ValueError(f"{owner}: GetExtremePoint failed")
                point = (x.value, y.value, z.value)
                coordinate = 1000.0 * (scale * sum(point[i] * rows[i][axis] for i in range(3)) + shift[axis])
                low[axis], high[axis] = min(low[axis], coordinate), max(high[axis], coordinate)
    for value in low + high:
        finite(value, "extent")
    return low, high


def _exact_geometry(items, val):
    """True when every face is analytic and every edge a line, circle or ellipse (budgeted; else False)."""
    seen = 0
    for _, body, _ in items:
        for face in val(body, "GetFaces") or ():
            seen += 1
            if seen > MAX_CLASSIFIED_ENTITIES:
                return False
            surface = val(face, "GetSurface")
            if not any(val(surface, test) for test in ANALYTIC_SURFACES):
                return False
        for edge in val(body, "GetEdges") or ():
            seen += 1
            if seen > MAX_CLASSIFIED_ENTITIES:
                return False
            curve = val(edge, "GetCurve")
            if not any(val(curve, test) for test in EXACT_CURVES):
                return False
    return True


def _native_metrics(doc, report, issues, val, call, byref_double):
    """Capture metrics with an explicit uncertainty and its basis, so checks can cite the capture directly."""
    kind, metrics, exact_box = report.get("type"), {}, None
    if kind not in ("part", "assembly"):
        return metrics, exact_box
    try:
        items = _solid_bodies(doc, kind, val, call, issues)
    except Exception as exc:
        items = []
        issues.append(f"solid body extraction failed: {type(exc).__name__}")
    try:
        exact = bool(items) and _exact_geometry(items, val)
    except Exception:
        exact = False
    rel = REL_EXACT if exact else REL_APPROXIMATE
    integral = (f"CAD B-rep integral: half the reported step plus {rel:g} x value, the measured numerical floor for "
                f"{'analytic faces bounded by lines, circles or ellipses' if exact else 'intersection or freeform edges and faces, or unclassified models'} "
                "(design-evidence). Excludes density assignment, unmodeled parts and manufacturing variation.")
    mass = report.get("mass", {})
    for key, unit in (("mass_kg", "kg"), ("volume_mm3", "mm3"), ("area_mm2", "mm2")):
        value = mass.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[key] = _metric(value, unit, 0.5 * 10.0 ** -MASS_DECIMALS[key] + rel * abs(value), integral)
    try:
        low, high = _exact_extents(items, call, byref_double)
        size = [round(h - l, LENGTH_DECIMALS) for l, h in zip(low, high)]
        exact_box = {"min": [round(v, LENGTH_DECIMALS) for v in low], "max": [round(v, LENGTH_DECIMALS) for v in high],
                     "size": size, "bodies": len(items)}
        step = 10.0 ** -LENGTH_DECIMALS
        basis = (f"Tight extent of {len(items)} solid bodies from IBody2.GetExtremePoint in the document frame: "
                 f"half the {step:g} mm reporting step plus 2 x {LINEAR_PRECISION_MM:g} mm kernel linear precision.")
        for axis, value in zip("xyz", size):
            metrics["extent_" + axis] = _metric(value, "mm", 0.5 * step + 2 * LINEAR_PRECISION_MM, basis)
    except Exception as exc:
        issues.append(f"exact extents unavailable: {exc}")
        for axis, value in zip("xyz", (report.get("box_mm") or {}).get("size", ())):
            metrics["extent_" + axis] = _metric(value, "mm", None,
                                                "approximate bounding box that may enclose more than the geometry; not usable for checks")
    errors = report.get("errors", [])
    truncated = len(errors) >= FEATURE_ERROR_LIMIT
    metrics["rebuild_errors"] = _metric(len(errors), "1", None if truncated else 0,
                                        f"list truncated at {FEATURE_ERROR_LIMIT}: at least this many" if truncated
                                        else "exact count of features and mates reporting rebuild errors")
    if kind == "part":
        metrics["solid_bodies"] = _metric(report.get("bodies_total", len(report.get("bodies", []))), "1", 0,
                                          "exact count of visible solid bodies")
    else:
        components = report.get("components", {})
        metrics["components"] = _metric(components.get("total", 0), "1", 0, "exact count of components at all levels")
        metrics["suppressed_components"] = _metric(components.get("suppressed", 0), "1", 0, "exact count of suppressed components")
        metrics["mates"] = _metric(report.get("mates", 0), "1", 0, "exact count of mate features")
    return metrics, exact_box


def capture_native(doc, max_features=1000, max_dimensions=3000, max_faces=5000):
    from ..com import val, call, features, byref_double
    from ..verification import model_report
    if doc is None:
        raise ValueError("no active SolidWorks document")
    report = model_report(doc)
    captured, dimensions, issues = [], 0, []
    try:
        configuration = doc.ConfigurationManager.ActiveConfiguration.Name
    except Exception as exc:
        configuration = None
        issues.append(f"configuration extraction failed: {type(exc).__name__}")
    tree = features(doc)
    for feat in tree[:max_features]:
        entry = {"name": feat.Name, "type": val(feat, "GetTypeName2"), "dimensions": []}
        try:
            display = val(feat, "GetFirstDisplayDimension")
            while display is not None and dimensions < max_dimensions:
                dim = call(display, "GetDimension2", 0)
                entry["dimensions"].append({"name": dim.FullName, "system_value_si": finite(dim.SystemValue),
                                            "type_code": int(val(dim, "GetType"))})
                dimensions += 1
                display = call(feat, "GetNextDisplayDimension", display)
            if display is not None:
                issues.append("dimension limit reached")
        except Exception as exc:
            issues.append(f"{entry['name']}: dimension extraction failed: {type(exc).__name__}")
        captured.append(entry)
    if len(tree) > max_features:
        issues.append("feature limit reached")
    topology, components, face_count = [], [], 0
    if report.get("type") == "part":
        try:
            for body in call(doc, "GetBodies2", 0, True) or ():
                item = {"name": body.Name, "faces": []}
                faces = val(body, "GetFaces") or ()
                for index, face in enumerate(faces):
                    if face_count >= max_faces:
                        issues.append("face limit reached")
                        break
                    face_count += 1
                    surface = val(face, "GetSurface")
                    observation = {"snapshot_local_index": index, "area_mm2": finite(val(face, "GetArea")) * 1e6}
                    if val(surface, "IsPlane"):
                        values = list(val(surface, "PlaneParams"))
                        observation.update(kind="plane", normal=values[:3], origin_mm=[v * 1000 for v in values[3:6]])
                    elif val(surface, "IsCylinder"):
                        values = list(val(surface, "CylinderParams"))
                        observation.update(kind="cylinder", axis=values[3:6], origin_mm=[v * 1000 for v in values[:3]], radius_mm=values[6] * 1000)
                    else:
                        observation["kind"] = "other_surface"
                    item["faces"].append(observation)
                topology.append(item)
        except Exception as exc:
            issues.append(f"surface extraction failed: {type(exc).__name__}")
    elif report.get("type") == "assembly":
        try:
            all_components = call(doc, "GetComponents", False) or ()
            for comp in all_components[:max_features]:
                transform = val(comp, "Transform2")
                components.append({"name": comp.Name2, "path": val(comp, "GetPathName"),
                                   "configuration": comp.ReferencedConfiguration,
                                   "suppressed": bool(val(comp, "IsSuppressed")),
                                   "transform_array_si": list(transform.ArrayData) if transform is not None else None})
            if len(all_components) > max_features:
                issues.append("component limit reached")
        except Exception as exc:
            issues.append(f"component extraction failed: {type(exc).__name__}")
    source_path = report.get("path")
    source_sha = None
    if source_path and Path(source_path).is_file():
        source_sha = digest(Path(source_path).read_bytes())
    metrics, exact_box = _native_metrics(doc, report, issues, val, call, byref_double)
    return {"capture_type": "solidworks-native", "captured": now(), "report": report, "configuration": configuration,
            "source_file_sha256": source_sha, "features": captured, "surface_observations": topology,
            "components": components, "metrics": metrics, "exact_box_mm": exact_box,
            "incomplete": bool(issues), "extraction_issues": issues,
            "limitations": ["Read-only snapshot: no rebuild, save, activation, or feature edits are performed.",
                            "System dimension values are in SolidWorks SI units; angular dimensions use radians. Type codes are retained.",
                            "Feature display dimensions may be absent when hidden; their visibility is never changed. No complete dimension/constraint recovery is implied.",
                            "Surface indices identify only this snapshot; cylinder surfaces do not alone identify a functional hole or shaft.",
                            "Saved-file hash excludes unsaved edits; snapshot report records unsaved_changes.",
                            "Suppressed/configuration-dependent geometry, constraints, free-form surfaces and original design intent need further inspection.",
                            "Mass depends on CAD density assignments; no physical mass or full-motion collision validation is implied.",
                            "Metric uncertainty covers CAD numerical resolution only (reporting step, kernel precision, declared integration floor); "
                            "cite metrics in checks with conditions that name the pose, configuration and exclusions."]}
