---
title: Design policy - a basis for every number
tags: policy, 정책, 근거, rationale, basis, default, 기본값, symmetry, 대칭, ratio, 1:1, preferred numbers, 표준수, renard, safety factor, 안전율, wall, 두께, fillet, 필렛, chamfer, 모따기, clearance, 간극, iteration, 반복
summary: Basis ladder, neutral quantitative defaults when no basis exists, default safety factors and geometry defaults.
---

# Design policy

## Basis ladder
Use the highest available basis for each decision and tag it in specs, script comments and reports:
1. **[req]** user requirement, or existing geometry/interface (measure it in the model).
2. **[std]** standard: ISO / KS / JIS / DIN (fits, threads, keys, bearings, gear modules, preferred numbers).
3. **[calc]** calculation with stated inputs (stress, deflection, bearing life, gear ratio, heat balance).
4. **[cat]** purchasable part: standard catalogue dimensions, or a MISUMI part number the user has verified.
5. **[dfm]** manufacturing rule for the chosen process.
6. **[heur]** engineering rule of thumb with a named source (e.g. bevel face width <= Re/3).
7. **[neutral]** no basis available: use a neutral quantitative default (next section) and keep it a parameter.

A number without a tag is a bug. If a value is a pure guess, tag it **[assume]**, keep it at the top of the script, and list it in the report.

## Neutral defaults
When nothing above applies, choose the value that carries the least hidden intent:
- **Symmetry** about the main planes and axes; center features on the part or on the interface they serve.
- **1:1**: equal sizes, equal spacing, equal wall thickness, gear ratio 1:1, equal margins.
- **Preferred numbers**: Renard R10 (1, 1.25, 1.6, 2, 2.5, 3.15, 4, 5, 6.3, 8 x 10^n), R20 for finer steps; otherwise whole millimetres (0.5 mm steps below 10 mm).
- **Equal angular spacing** for patterns (360/n), n = 3 for small round parts, 4 for square/rectangular ones, 6 for larger flanges.
- **Same material and process** as the neighbouring parts.
- **Minimum standard part** that satisfies the requirement (smallest bearing, shortest standard screw).

## Geometry defaults
| Item | Default | Basis |
|---|---|---|
| Internal corner radius (milled) | R >= 1 mm, deep pockets R >= depth/6 | [dfm] cutter radius |
| External edges | C0.5 chamfer (machined), R0.5 (printed) | [dfm] deburr / handling |
| Wall thickness | Al >= 2 mm, steel >= 1.5 mm, FDM >= 2 mm (5 perimeters of 0.4) | [dfm] |
| Running clearance between moving parts | 0.5 mm machined, 0.3-0.4 mm FDM | [heur] |
| Shaft-hole fits | H7/g6 running, H7/h6 sliding, H7/k6 located, H7/p6 pressed | [std] ISO 286 |
| General tolerance | ISO 2768-m | [std] |
| Fastener size | smallest of M3/M4/M5/M6 meeting the load; >= 2 per joint | [neutral] + [calc] |
| Bolt hole | ISO 273 medium clearance | [std] |
| Thread engagement | 1d steel, 1.5-2d aluminium, inserts for plastics | [heur] |

## Safety factors
- Static, known loads, ductile metal: 2.0 on yield.
- Uncertain loads, impacts, plastics, printed parts: 3.0 on yield (printed: use the weaker Z-direction strength).
- Fatigue: 1.5 on the endurance limit; robot joints: design for peak torque x 1.5.
- Buckling: 3.0 on the critical load.

## Iteration policy
- Every iteration is a complete, valid model that passes the quality gate (agent-guide), even if simplified (e.g. a gear blank before the teeth).
- Change one group of parameters per iteration and report the delta and its effect (mass, clearance, stress).
- Keep designs parametric: parameters at the top of scripts or SolidWorks global variables/equations, so the next iteration changes numbers, not geometry code.
- Stop iterating when the requirement is met with margin; report the margin.
