"""Read-only geometry observations; never infer original feature intent."""
import math
import re
import struct
from collections import Counter
from pathlib import Path
from .common import digest, finite, now


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
            "metrics": {"extent_x": {"value": high[0] - low[0], "unit": "mm"},
                        "extent_y": {"value": high[1] - low[1], "unit": "mm"},
                        "extent_z": {"value": high[2] - low[2], "unit": "mm"}},
            "limitations": ["Exact coincident-vertex edge test; no welding tolerance is applied.",
                            "Closed edges/winding do not prove no self-intersections or overlapping/disconnected shells; volume is provisional.",
                            "Mesh geometry does not recover original dimensions, tolerances, materials, design intent or native feature history."]}


def capture_native(doc, max_features=1000, max_dimensions=3000, max_faces=5000):
    from ..com import val, call, features
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
    metrics = {}
    for key, unit in (("mass_kg", "kg"), ("volume_mm3", "mm3"), ("area_mm2", "mm2")):
        if key in report.get("mass", {}):
            metrics[key] = {"value": report["mass"][key], "unit": unit}
    if report.get("type") == "part":
        metrics["solid_bodies"] = {"value": report.get("bodies_total", len(report.get("bodies", []))), "unit": "1"}
    if report.get("box_mm"):
        for axis, value in zip("xyz", report["box_mm"]["size"]):
            metrics["extent_" + axis] = {"value": value, "unit": "mm"}
    return {"capture_type": "solidworks-native", "captured": now(), "report": report, "configuration": configuration,
            "source_file_sha256": source_sha, "features": captured, "surface_observations": topology,
            "components": components, "metrics": metrics,
            "incomplete": bool(issues), "extraction_issues": issues,
            "limitations": ["Read-only snapshot: no rebuild, save, activation, or feature edits are performed.",
                            "System dimension values are in SolidWorks SI units; angular dimensions use radians. Type codes are retained.",
                            "Feature display dimensions may be absent when hidden; their visibility is never changed. No complete dimension/constraint recovery is implied.",
                            "Surface indices identify only this snapshot; cylinder surfaces do not alone identify a functional hole or shaft.",
                            "Saved-file hash excludes unsaved edits; snapshot report records unsaved_changes.",
                            "Suppressed/configuration-dependent geometry, constraints, free-form surfaces and original design intent need further inspection.",
                            "Mass depends on CAD density assignments; no physical mass or full-motion collision validation is implied."]}
