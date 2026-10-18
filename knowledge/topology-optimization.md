---
title: Topology optimization (topology_optimize)
tags: topology optimization, topology, 토폴로지, 위상, 최적화, optimisation, lightweight, 경량, 경량화, stiffness, 강성, compliance, simp, topy, mechanism, 메커니즘, compliant, 컴플라이언트, bracket, 브라켓, volume fraction, 부피율, keep out, 금지영역, keep in, filter, 필터
summary: Setting up 2D/3D minimum-compliance and compliant-mechanism problems in mm, defaults with their basis, reading the results and turning them into SolidWorks parts.
---

# Topology optimization

## What it does
- SIMP density method (Python 3 / scipy port of ToPy, verified against Sigmund's 99-line code): minimum compliance (maximum stiffness for a volume budget) or compliant mechanisms, 2D plane-stress plates or 3D solids. Thermal and CFD problems are not included.
- Runs as a background job; `topology_optimize` waits up to `wait` s (default 25, max 30), then poll with `job`. `build: true` creates the part: 2D -> splines through the 0.5-density contour, extruded by the thickness (volume checked); 3D -> STL imported as a mesh solid body (reference geometry to remodel with features).

## Problem spec (mm, origin at the lower-left(-back) corner, y up)
```json
{"size": [120, 60], "element_size": 1, "thickness": 6, "volume_fraction": 0.4,
 "supports": [{"edge": "left", "fix": "xy"}],
 "loads": [{"at": [120, 30], "force": [0, -1000]}],
 "keep_out": [{"circle": [30, 30, 10]}], "keep_in": [{"circle": [110, 30, 6]}],
 "material": {"E": 70000, "nu": 0.33, "density": 2.7}}
```
- Selections: `at` (nearest node), `box` [x0, y0, x1, y1] (3D: 6 values), `edge` left/right/bottom/top, `face` x0/x1/y0/y1/z0/z1. `fix` lists the fixed directions ("x", "xy", "xyz").
- Loads in N, split equally over the selected nodes. Spread point loads over a small box (a bolt or pin footprint) to avoid single-node stress spots.
- `keep_out` (void) and `keep_in` (solid): box, circle, sphere, cylinder {center, axis, radius, length}. Put keep_in rings around bolt holes and bearing seats, keep_out where other parts move.
- Mechanism: `"type": "mechanism"`, input = the load, `"output": {"at": [...], "direction": [dx, dy]}`; the result moves the output that way.
- ToPy files: pass `tpd` (text or path) for any ToPy v2007 problem (comp or mech; heat is rejected).

## Defaults and basis
| Item | Default | Basis |
|---|---|---|
| Volume fraction | 0.5 | [neutral] 1:1 solid:void when no mass target is given |
| Penalty p | 3 | [heur] SIMP standard (Sigmund 2001, ToPy) |
| Filter radius | 1.5 elements | [heur] Sigmund 99-line / ToPy; set filter_radius_mm >= the smallest member you can make |
| Approximation ETA | 0.5 (reciprocal) | [heur] same OC update as the 99-line code |
| Elements | Q4 (2D), H8 (3D); Q5B/H18B for bending | [heur] ToPy |
| Resolution | about 6000 (2D) / 8000 (3D) elements | [neutral] run time |
| Stop | 60 (2D) / 40 (3D) iterations or change < 0.01 | [heur] 99-line stop rule |

## Run time (measured)
- 2D 120 x 60 (7200 elements): about 4 s for 50-65 iterations. 2D is cheap; 20-40k elements are fine.
- 3D 40 x 20 x 10 (8000 elements, 28k DOF): about 0.7 s per iteration (CG with warm start). Keep 3D under about 30k elements, or use 2D plates where the part is plate-like.

## Reading the result
- `summary.volume` must equal the volume fraction; `change` < 0.01 means converged; `grey_fraction` (0.1 < density < 0.9) under about 0.1 is crisp, above 0.2 refine the mesh or raise the iterations.
- `physical` (when E is given): compliance N mm, largest load-point displacement mm, mass g. Compare designs at the same volume fraction.
- `cad` (2D): loops, holes, area and plate volume; the extruded part's `volume_error_pct` should be within about 0.1 %.
- Check the preview: supports blue, loads red, mechanism output green. Members thinner than 2 elements are not manufacturable at that element size.

## Turning it into a part
1. Optimise on a design space that already excludes interfaces (keep_out) and protects them (keep_in).
2. Build the plate (`build: true`), then add the real interface features: bolt holes, bearing bores, chamfers/fillets (dfm), and check wall thickness against the process.
3. For 3D results remodel the load paths with ribs, pockets and fillets around the imported mesh body, then delete or hide the mesh.
4. Verify the final part: mass, and if needed a FEA in SOLIDWORKS Simulation with real loads.
