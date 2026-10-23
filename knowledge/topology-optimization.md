---
title: Topology optimization (topology_optimize)
tags: thermal, 열, 열전도, 대류, convection, heat, 방열, safety factor, 안전율, 안전계수, joint, 체결부, bolt, 볼트, tapped hole, 탭, interface, 접합, machining, 가공, milling, topology optimization, topology, 토폴로지, 위상, 최적화, optimisation, lightweight, 경량, 경량화, stiffness, 강성, compliance, simp, topy, mechanism, 메커니즘, compliant, 컴플라이언트, bracket, 브라켓, volume fraction, 부피율, keep out, 금지영역, keep in, filter, 필터
summary: Setting up 2D/3D stiffness, heat-conduction (with convection) and combined problems in mm with the 2 x safety factor on joints, defaults with their basis, reading the results and turning them into SolidWorks parts; machining mode plan.
---

# Topology optimization

## What it does
- SIMP density method (Python 3 / scipy port of ToPy, verified against Sigmund's 99-line code): minimum compliance (maximum stiffness for a volume budget), compliant mechanisms, steady heat conduction with convection films, or stiffness and heat together; 2D plane-stress plates or 3D solids. Fluid flow (CFD) is not modelled: convection enters as a film coefficient.
- Every spec run uses design values = `safety_factor` (default and minimum 2) x the maximum force and heat, sizes joint holes and keep-in rings, and ends with stress, temperature and per-joint checks (sections below).
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

## Safety factor 2 on joints and critical features
- Rule [req, user]: joints with other parts (bolts, tapped holes, pins, contact and thermal pads) and critical features are designed for 2 x the maximum force and 2 x the maximum heat. Enter maximum service loads and heat; the solver, the preview arrows and every check use the design values. `safety_factor` may be higher, never below 2 (error).
- `interfaces` turn each joint into geometry and boundary conditions: hole (ISO 273 medium clearance for `bolt`, ISO 2306 tap drill for `tapped`, the pin diameter for `pin`) as keep-out, a keep-in ring of radius max(1.5 d, washer seat (ISO 7089) + one element), and the nodes of the hole wall as a support (`role: support`), a design load (`role: load`, `force`), a heat source (`heat_W`) or a sink at the reference temperature (`sink: true`). A `pad` (box, circle, cylinder) is kept solid and carries the same roles.
- `critical` shapes (bearing seats, sealing faces, datum bosses) stay solid; give a `reason`.
- Joint checks at the design force (supports use the computed reaction): bolt or pin shear (ISO 898-1 Rp0.2/sqrt 3, stress area), bolt tension when `axial`, part bearing <= yield, tear-out edge distance against the ring radius, and for tapped holes the engagement needed so the thread does not strip before the bolt yields (0.75 pi d L, at least 1 d). A failing joint is a SPEC issue for the next loop: larger size, more bolts, thicker plate or a stronger material; the optimiser does not move joints.
- Field checks: von Mises screening (elements with density >= 0.5, qp-relaxed, joints excluded) <= yield at the design load, i.e. at least 2 x margin at the maximum load (`sf_at_max_load`), and peak temperature at the design heat <= `max_temperature_C`. Screening is not FEA of the final CAD: verify the built part in SOLIDWORKS Simulation at the design loads.
- `volume_fraction: "auto"` bisects (`auto_range`, `auto_steps`) for the lightest design whose field checks pass. Keep-in regions above the volume fraction are rejected: there is nothing left to optimise.

## Thermal and stiffness+thermal mode
```json
{"size": [80, 50], "element_size": 1, "thickness": 4, "volume_fraction": "auto",
 "material": {"E": 69000, "nu": 0.33, "yield": 240, "density": 2.7, "k": 167},
 "interfaces": [{"type": "bolt", "size": 5, "at": [8, 10], "role": "support", "sink": true},
                {"type": "bolt", "size": 5, "at": [8, 40], "role": "support", "sink": true},
                {"type": "tapped", "size": 4, "at": [72, 25], "role": "load", "force": [0, -300]},
                {"type": "pad", "box": [40, 20, 52, 30], "role": "thermal", "heat_W": 4}],
 "thermal": {"reference_C": 40, "max_temperature_C": 85, "plate_faces": {"h_W_m2K": 8, "sides": 2}}}
```
- Temperatures are solved as theta = T - `reference_C`: sinks sit at the reference, films exchange heat with it. One reference per problem; take the hottest of ambient and mounting temperature when they differ.
- Films: `convection` on domain edges (2D, through the thickness) or faces (3D), fixed; `plate_faces` (2D) puts the film on both plate faces wherever material exists (density-weighted). Interior film in 3D (design-dependent surfaces) is not modelled.
- Objective: w_s C_s / C_s0 + w_t C_t / C_t0, each compliance normalised by its first-iteration value (`objective` weights, default 1:1). Both terms are self-adjoint.
- Checked against closed forms (2026-10-23): conduction bar within 0.2 % (equal nodal split at the corners), plate-face film energy balance and edge film exact, uniaxial stress exact; a 64 x 40 x 8 mm 3D aluminium bracket with 6 W design heat rose 9.4 K, the order of a hand estimate (10-15 K).

## Machining mode (planned, not implemented)
Goal: results that a CNC machine can cut. Plan from the 2026-10-23 code survey (leads, not independently verified):
- No usable open-source implementation exists; re-implement. Per tool direction a smooth cumulative filter along the tool axis followed by a Heaviside projection gives 2.5D milling (Langelaar 2019, CMAME 351:226); several setups combine by a smooth intersection. Minimum tool radius = void length scale (filter + eroded/dilated robust projection), wall = solid length scale, floor = passive layer, extrusion = project to 2D and re-extrude (Vatanabe et al. 2016, AES 100:97). Casting direction: Gersborg and Andreasen 2011, SMO 44:875.
- Code templates: pyMOTO (MIT, aatmdelissen/pyMOTO) overhang filter; BESO (LGPL, calculix/beso) casting filter and topoptlab (GPL) as reference only. Verify accessibility of the final voxels by ray casting before CAD export; pocket and rib parameter studies later on the same FE core.
- The safety-factor rule and the joint handling above apply unchanged.

## Turning it into a part
1. Optimise on a design space that already excludes interfaces (keep_out) and protects them (keep_in); declare joints as `interfaces` so holes, rings and checks follow the 2 x rule.
2. Build the plate (`build: true`), then add the real interface features: bolt holes, bearing bores, chamfers/fillets (dfm), and check wall thickness against the process.
3. For 3D results remodel the load paths with ribs, pockets and fillets around the imported mesh body, then delete or hide the mesh.
4. Verify the final part: mass, and FEA in SOLIDWORKS Simulation at the design loads and heat (2 x maximum); the optimiser's checks are screening only.
