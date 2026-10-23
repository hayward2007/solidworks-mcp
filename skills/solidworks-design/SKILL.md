---
name: "solidworks-design"
description: "Use when designing, modeling or changing SolidWorks parts or assemblies through the solidworks connector (gears, brackets, lightweight parts, mechanisms)."
---

# SolidWorks design with the solidworks connector

The connector's own working rules are sent as MCP server instructions, but Cowork does not pass those on. This skill brings them in.

## 0. Check the connector
If only `design_*` tools are available, the portable investigation/retrieval/review workflow is ready. Use it normally; native CAD capture and modeling additionally require the Windows SolidWorks server.
If no solidworks tools (`execute_python`, `knowledge_get`, `gear_design`, ...) are available, the connector is not installed or Claude Desktop was not restarted after installing it. Do not try to model another way: point the user to the one-line install in https://github.com/hayward2007/solidworks-mcp (they can simply ask Claude to install it), then to fully quitting Claude Desktop from the tray icon and starting it again.

## 1. Load the rules once per task
- If `design_context` is available, start in `mode="quality"`, then `design_schema`. Use portable Design Studio for evidence, retrieval, proposals and review, and the Windows server for native CAD.
- Load `product-design-policy`, `design-evidence` and `design-review` through `knowledge_get` when only legacy tools are exposed. These supersede older token-first defaults.
- `knowledge_get("agent-guide")`: build-verify loop, token rules, quality gate, report format.
- `knowledge_get("design-policy#basis-ladder")` and `knowledge_get("design-policy#neutral-defaults")`.
- Anything else (gears, bearings, fasteners, fits, shafts and keys, materials, DFM, API recipes): `knowledge_search` first, then `knowledge_get` for one section only.

## 2. Complete specification before geometry
Purpose, envelope, interfaces (mating parts, shafts, bolt patterns), loads and motion, process and material, the numbers to hit.
Also record baseline hashes, datums, protected interfaces, profiles/placements/sections, tolerances, manufacturing/assembly/service, three alternatives and visual criteria (silhouette, proportions, radius hierarchy, seams, CMF). No specification length cap. Distinguish measured facts, reported claims and assumptions; a basis tag alone does not verify a standard or catalogue value.
For product improvement, `design_submit` recomputes gates and `design_review_packet` exports the complete review. Wait for a real user review before `design_handoff`. Never execute the human-only review CLI for the user. This workflow does not replace direct user authorization for independent routine CAD operations.
Tag every number with its basis: [req] requirement or existing geometry > [std] ISO/KS/JIS > [calc] > [cat] catalogue or user-verified MISUMI part > [dfm] > [heur] > [neutral] (symmetry, 1:1, equal spacing, Renard R10, whole mm). An untagged number is a bug.
For vague requests, read the open documents and existing geometry first, state assumptions in one line and continue; ask only when the answer changes the concept.

## 3. Use the dedicated tools first
- Gears: `gear_design` (numbers and warnings, no CAD), then `create_gear`. Use `build_mate: true` for pairs and check `volume_error_pct` (|e| < 0.1 %), `bodies` = 1 and `mesh_check.max_interference_mm3` (about 0 with backlash). External helical and spiral bevel pairs need opposite hands; internal helical and worm/wheel pairs the same hand.
- Lightweight parts: `topology_optimize` with the problem in mm (supports, loads, keep_in around bolt holes, keep_out for moving parts, material). Poll with `job`, then `build: true` and add the interface features.
- Everything else: `execute_python`, one modeling stage per call, parameters at the top, injected helpers (`val`, `call`, `arr`, `select`, `plane`, `feats`, `report`, `render`, `store`, `mm`, `deg`). API units are metres and radians.

## 4. Verify every stage
- `report()` inside the script or `model_report`: no rebuild errors, intended body count, box and mass as expected.
- Obtain enough consistent orthographic, section and material views to judge geometry and styling. Do not reduce decisive evidence to save tokens; this system does not measure provider image token cost.
- Assemblies: `check_interference` must be 0 except intended press fits.
- Fix the first failure only; after 3 failed attempts on one stage change the approach.

## 5. Respect the user's open work
Do not modify, save or close documents the user already has open unless asked. Build trials in new parts, close them afterwards and re-activate the user's document.

## 6. Report
Key parameters with basis tags, the check numbers, open issues and at most 3 next options. Print only counts and key values, never whole trees or point lists.
