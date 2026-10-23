---
title: SolidWorks assembly procedure (A0-A8) and known pitfalls
tags: assembly, 어셈블리, 조립, mate, 메이트, gear mate, 기어 메이트, lock, 고정, fixed, 고정 부품, datum, 기준, reference axis, 기준축, pose, 자세, kinematic, 기구학, motion, 동작, interference, 간섭, render drift, 자세 변화, transform, MateGroup, close window, 창 닫기, 리소스, timeout, 타임아웃
authority: internal_guide
source: repository:knowledge/assembly-guide.md (differential and gear sessions, SOLIDWORKS 2025 Korean UI, 2026-10)
checked: 2026-10-23
applicability: Assemblies built or verified through the SolidWorks MCP server; read with design-workflow and solidworks-api
summary: Fixed assembly steps with entry/exit checks, the mate and pose rules that cost the most time, and how to verify motion without open-ended solver experiments.
---

# Assembly procedure

Every step ends with a check. Do not start the next step while the previous check fails.
Record each failure as an issue (design-workflow#issue-log) before trying a fix.

## A0 Plan the assembly before inserting anything
- Write the assembly table: component, file, grounded or mated, intended degrees of freedom,
  mates (type, entities by datum name), and the motion law (for example side R = 2 case - side L).
- Fix the frame: assembly X forward, Y left, Z up; origin on the main joint axis. Functional
  datums that several parts share (an apex plane, a pitch plane, an axle axis) become
  assembly-level reference geometry, created first.
- Choose the verification set now: the rest pose, 2-4 poses along the motion law, one control
  pose that must fail (for example a reversed drive sense), and the interference policy
  (intended press fits, known tooth-approximation residue, coincident contact not counted).
- One component is grounded (fixed). Any other fixed component is a documented parking choice.

## A1 Part readiness (per part, before it enters the assembly)
- `report()`: no rebuild errors, one solid body, expected box and mass, material assigned with
  its localized database name (Korean: "AISI 4340 강, 강화", "AISI 1045 강, 냉간압연", "AISI 1020").
- Named reference geometry for every mating function: axes (`Bore axis`, `Pin axis`) and planes
  (`Apex plane`, `Mount face`). Mates select these by name, not by picking faces at coordinates.
- Positions derived from exact part geometry, not rounded numbers. A ring apex placed with a
  0.001 mm rounding produced a 1.83 mm3 overlap with the case flange.
- Save, then close the part window. Keep only the assembly window open while assembling:
  SolidWorks loads referenced parts without windows, and each extra window costs memory and
  redraw time. Never close or save a document the user opened.

## A2 Create the assembly
- New assembly from the template, save it at once under its final name in the project folder.
- Insert the base component, align it with the assembly frame (mate its planes to the
  assembly planes or place it with `Transform2` before any mate exists), then fix it.
- Create the shared assembly datums from A0 now.

## A3 Insert and mate one component at a time
- Insert near its pose. `Transform2` is fine before the component has mates; after that,
  only mates move it.
- Mates: `AddMate5`; error status 1 is success. Axis to axis: coincident (kind 0); concentric
  (kind 1) failed for two reference axes. Plane to plane: coincident or distance. Phase or
  clocking: angle (kind 6). Gear: kind 10 with the tooth counts as ratio. Lock: kind 16.
- If a part datum cannot be mated to another part datum (a part plane against a case plane
  failed), mate it to the assembly datum instead.
- Find a new mate with `FeatureByName` or by comparing the feature list before and after. Never
  rename "the last feature" in an assembly: `FeatureByPositionReverse(0)` is the MateGroup
  (Korean name 메이트), and renaming it silently renames the mate folder.
- After each component: rebuild, `report()["errors"]` empty, interference of this component
  against its neighbours. Fixing an overlap now costs one parameter; finding it at the end
  costs a search.

## A4 Kinematic mates
- A gear mate locks the phase that exists when it is created: set the mesh phase first
  (from `gear_design`, for example a side gear phase of 11.25 deg), then add the gear mate.
- `ForPositioningOnly` angle mates did not move components reliably: use a real angle mate
  and delete it afterwards.
- Edit an existing mate through its definition: `def = val(mate, "GetDefinition")`, change
  `def.Angle` (radians) or `def.Reverse`, then `call(mate, "ModifyDefinition", def, asm, NOCALL)`.
- Solver check: drive the input with a temporary angle mate at two angles and read the output
  transforms. At most two attempts (about 15 minutes). The differential side gears followed
  the solver exactly, but the spiral bevel final-drive gear mate turned the wrong way or not at
  all for every entity and flip choice tried, and dragging did not help either. When the
  solver does not reproduce the law, stop, log a TOOL issue and use the geometric pose test (A6).

## A5 Parking pose for review, render, capture and save
- An under-defined assembly can move when it is rebuilt or rendered: a render changed the case
  angle to 24.78 deg before a capture. Before render, capture or save, remove the free degrees of
  freedom: fix the driving components (and say so in the report), or add a temporary lock or
  angle mate.
- Read the moving components' transforms before and after the render; any change is a defect.

## A6 Motion and interference verification
Use one method per assembly and the same pose table each loop.
- Solver method (when A4 passed): drive the input angle mate through the pose table, run
  `check_interference` at each pose.
- Geometric method (when the solver cannot carry a gear pair): save first, suppress the gear
  mates, write the transforms of all moving components from the motion law in one script,
  run `check_interference`, then close without saving and reopen. Writing `Transform2` on mated
  components re-baselines lock and gear mates, so never keep those poses.
- Report per pose: pose values, total volume, pairs with volume, and the allowed residue with
  its basis. The control pose must fail clearly (reversed final-drive sense: 120.474 mm3 against
  a 0.176 mm3 residue), otherwise the check does not discriminate.
- One pose is not a motion sweep; state the number of poses.

## A7 Evidence and close-out
- `design_capture` of the parked assembly: metrics now carry uncertainty and can be cited
  directly. Note `report.unsaved_changes`; save first when the evidence must match the file.
- Renders: the same view set every loop (iso, front, top, right, plus sections when needed).
- Save the assembly, close every part window opened during the work, list the open documents
  in the report. A long call that times out on the device (60 s) may still finish: check
  `list_open_documents` or `store` before running it again.

## Pitfalls seen (symptom -> cause -> fix)
| Symptom | Cause | Fix |
|---|---|---|
| Mate folder renamed | renamed `FeatureByPositionReverse(0)` in an assembly | `FeatureByName`, feature list diff |
| Concentric mate error 0 between two axes | concentric needs cylindrical faces | coincident (kind 0) on the axes |
| Gear phase or lock angle changed after a pose test | `Transform2` written on mated components | pose tests with gear mates suppressed, close without saving |
| Output gear does not follow the input | API solver and drag do not carry that gear mate | two attempts, then geometric pose test (A6) |
| Component moved after render or capture | under-defined assembly re-solved on rebuild | park: fix the driving components or lock them |
| Tiny interference at a seat | datum placed with a rounded number | place from exact part geometry |
| Device call timed out | long open or interference run | check state first; do not re-run blindly |
| Many slow windows | finished parts left open | save and close each part after A1 |
