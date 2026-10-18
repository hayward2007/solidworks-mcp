---
title: SolidWorks API recipes (verified on SolidWorks 2025)
tags: solidworks, 솔리드웍스, api, com, recipe, 레시피, sketch, 스케치, extrude, 돌출, revolve, 회전, loft, 로프트, sweep, pattern, 패턴, mirror, 대칭, configuration, 구성, assembly, 어셈블리, mate, 메이트, gear mate, 기어메이트, interference, 간섭, mass, 질량, export, 내보내기, korean, 한국어, localized
summary: Calls and argument lists that are known to work through this server, plus the COM and localization pitfalls that waste the most attempts.
---

# SolidWorks API recipes

## Rules that prevent most failures
- Late binding: read zero-argument members with `val(obj, "Name")`, call methods that take arguments with `call(obj, "Name", ...)`. Never write `obj.GetType()`.
- The API uses metres and radians (`mm`, `deg` helpers).
- Localized UI: default planes and origin are named per language (Korean: 정면, 윗면, 우측면, 원점). Use `plane("front")`. Feature type names (`GetTypeName2`) are language independent.
- Named views like "*Isometric" fail in localized UI: use view ids, `call(doc, "ShowNamedView2", "", 7)` (1 front, 2 back, 3 left, 4 right, 5 top, 6 bottom, 7 iso).
- After creating a feature, rename it right away: `call(doc, "FeatureByPositionReverse", 0).Name = "..."`.
- Signatures: `pythoncom.LoadTypeLib(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb")`; enum values in `swconst.tlb`.

## 2D sketch and revolve
```python
sm = doc.SketchManager
select(doc, plane("front"), "PLANE")
call(sm, "InsertSketch", True)                       # enter sketch
for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
    call(sm, "CreateLine", x1 * mm, y1 * mm, 0, x2 * mm, y2 * mm, 0)
call(sm, "CreateCenterLine", -5 * mm, 0, 0, 40 * mm, 0, 0)   # revolve axis
call(sm, "InsertSketch", True)                       # exit
sk = call(doc, "FeatureByPositionReverse", 0)
call(sk, "Select2", False, 0)
rev = call(doc.FeatureManager, "FeatureRevolve2", True, True, False, False, False, False, 0, 0,
           2 * math.pi, 0, False, False, 0, 0, 0, 0, 0, True, True, True)
```
- Do not set `sm.AddToDB = True` right after `InsertSketch` in a 2D sketch: lines were silently not created. Default inference merges shared endpoints; check `len(val(val(sm, "ActiveSketch"), "GetSketchContours"))`.

## 3D sketch splines
```python
call(sm, "Insert3DSketch", True); sm.AddToDB = True
call(sm, "CreateSpline2", arr([c * mm for p in points for c in p]), False)
call(sm, "CreateLine", *a, *b)                       # metres, shared endpoints merge
sm.AddToDB = False; call(sm, "Insert3DSketch", True)
```

## Loft cut with guide curves
```python
call(doc, "ClearSelection2", True)
for f in profiles: call(f, "Select2", True, 1)     # mark 1, in order
for g in guides:   call(g, "Select2", True, 2)     # mark 2
cut = call(doc.FeatureManager, "InsertCutBlend", False, False, False, 1.0, 0, 0, False, 0, 0, 0, True, True)
```
- Profiles built from the same segment sequence still mis-match when consecutive sections are rotated more than about half the profile width; guide curves through matching corners fix it.

## Axis, circular pattern, mirror, delete body
```python
select(doc, plane("front"), "PLANE"); select(doc, plane("top"), "PLANE", append=True)
call(doc, "InsertAxis2", True)                       # X axis from two planes
call(axis, "Select2", False, 1); call(cut, "Select2", True, 4)
call(doc.FeatureManager, "FeatureCircularPattern5", n, 2 * math.pi, False, "NULL", False, True,
     False, False, False, False, 1, 0.0, "NULL", False)
select(doc, plane("front"), "PLANE", mark=2); select(doc, body_name, "SOLIDBODY", append=True, mark=256)
call(doc.FeatureManager, "InsertMirrorFeature2", True, False, False, False, 0)   # mirror body
select(doc, body_name, "SOLIDBODY"); call(doc.FeatureManager, "InsertDeleteBody2", False)
```

## Configurations
```python
cm = doc.ConfigurationManager
call(cm, "AddConfiguration2", "LH", "comment", "", 0, "", "", True)   # becomes active
# ... add features ...
call(feature_obj, "SetSuppression2", 0, 3, strings(["기본"]))       # suppress in a named configuration
call(doc, "ShowConfiguration2", "기본")
```
In an assembly: `component.ReferencedConfiguration = "LH"` then `val(asm, "EditRebuild3")`.

## Assembly placement and mates
- Component pose: rows of `Transform2.ArrayData[0:9]` are the component X, Y, Z axes in assembly coordinates, `[9:12]` the origin (metres). Set with `comp.Transform2 = call(val(sw, "GetMathUtility"), "CreateTransform", arr(rows + origin + [1, 0, 0, 0]))`.
- Selection strings: `f"Point1@원점@{comp}@{asm_title}"` type `EXTSKETCHPOINT`; `f"{axis}@{comp}@{asm_title}"` type `AXIS`; assembly origin `"Point1@원점"`.
- `call(asm, "AddMate5", kind, align, flip, dist, 0, 0, ratio_num, ratio_den, angle, 0, 0, positioning_only, lock_rotation, 0, byref_int())` with kind 0 coincident, 1 concentric, 2 perpendicular, 3 parallel, 5 distance, 6 angle, 10 gear. The error status 1 means success.
- A gear mate locks the phase that exists when it is created: set the mesh phase first.
- `ForPositioningOnly` angle mates did not move a component reliably; use a temporary real mate and delete it.

## Checks without changing the model
```python
mp = val(doc.Extension, "CreateMassProperty")          # Volume m3, Mass kg, CenterOfMass
body_copy = val(body, "Copy"); call(body_copy, "ApplyTransform", transform)
hit = call(val(body, "Copy"), "Operations2", 15901, body_copy, byref_int())   # temporary intersect
```
Temporary body booleans are fast (about 0.3 s for two gears) and accept mirror transforms; use them to test meshes or clearances before adding features.

## Images and export
- `render_views` / `render()` hide sketches, planes and axes, save PNGs, return one small grid, and restore the user's view.
- `export_model` uses Save As copy (STEP, STL, 3MF, IGES, Parasolid, PDF for drawings).

## Gears, sweeps, imports (verified on SolidWorks 2025)
- 2D sketch with `sm.AddToDB = True` after `InsertSketch`: arcs, splines and lines are created exactly (no snapping) and about 2x faster; shared end points form one contour (check `len(val(sk, "GetSketchContours"))`). If entities are missing, retry with AddToDB False.
- Cut sweep with constant twist: `call(fm, "InsertCutSwept5", False, True, 8, False, False, 0, 0, False, 0, 0, 0, 0, True, True, twist, True, False, False, False, False, 0, 0)` (profile mark 1, path mark 4, twist in radians, sign honoured). The twist is silently dropped when the path (the gear axis) runs inside the body: keep the axis in air (construction bore) and add the hub afterwards.
- A sweep starts at the path end nearer the profile; start translation paths at the middle of the profile, or the result goes the opposite way.
- Probe material without changing the model: `call(modeler, "CreateBodyFromCyl", arr([x, y, z, ax, ay, az, r, h]))` (base centre, axis, radius, height) and intersect with `call(body.Copy, "Operations2", 15901, tool, err)`; err 0/1 is success, anything else is a failed boolean (do not read it as zero volume).
- Body poses for checks: `ApplyTransform` with rows = images of the X, Y, Z axes, then the translation (metres).
- Revolve cut (e.g. a worm-wheel throat torus): `FeatureRevolve2(True, True, False, True, ...)`.
- Splines through sparse points overshoot on straight runs: split closed contours at corners and resample every ~1 element before `CreateSpline2`.
- STL as a solid body: set `SetUserPreferenceIntegerValue(208, 2)` (solid), `(210, 0)` (mm) and toggle 679 = True (mesh BREP), then `LoadFile4(path, "r", GetImportFileData(path), err)`; restore the preferences afterwards. With toggle 679 False the STL becomes a surface body.
