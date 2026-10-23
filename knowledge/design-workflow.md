---
title: Design - model - verify flywheel with standard verification batteries
tags: workflow, 워크플로, flywheel, 플라이휠, loop, 루프, iteration, 반복, design, 설계, modeling, 모델링, verification, 검증, battery, 검증 절차, issue, 이슈, triage, 분류, time box, 시간 제한, stop rule, report, 보고, safety factor, 안전율, close window, 창 닫기
authority: internal_guide
source: repository:knowledge/design-workflow.md (lessons from the differential session, 2026-10)
checked: 2026-10-23
applicability: Every SolidWorks design task through this server; product-design-policy, design-evidence and design-review still govern evidence and human review
summary: Each loop runs Design, Model, Verify and Triage with fixed gates, fixed check batteries and time boxes; every failed check becomes a classified issue that feeds the next loop or the procedures themselves.
---

# Design - model - verify flywheel

Verification is not shortened. It is made routine: the same batteries in the same order with
the same output rows, time boxes on open-ended work, and every failure written down as an issue
with a class and a destination. Problems then show up as rows, not as a long search.

```
 D design/spec --> M model --> V verify --> T triage --+--> next loop: D (spec issues)
       ^                                                +--> next loop: M (model, assembly issues)
       |                                                +--> procedures: guide, battery, tool (method, tool issues)
       +------------------ loop report <----------------+
```
A loop ends with a loop report. The flywheel effect: TOOL and METHOD issues change the guides,
batteries or tools in the same loop, so the next task does not pay for them again.

## Stage D: design and specification
Output: the spec ledger (product-design-policy), plus three items that make V mechanical:
- Requirement table with metric ids. Use capture metric names where they apply (`mass_kg`,
  `extent_x`, `rebuild_errors`, `solid_bodies`, `components`, `mates`), so verification rows and
  Design Studio checks cite the capture directly (design-evidence#capture-metrics-usable-in-checks).
- Load and heat cases with their maximum values and the design values. Joints (bolts, tapped
  holes, pins, keys, press fits, bonded or clamped faces) and other critical features are
  designed for 2 x the maximum force and 2 x the maximum heat load unless the brief sets another
  factor; the optimization modes apply this automatically (topology-optimization#safety-factor-2-on-joints-and-critical-features).
- Verification plan: which batteries run, the limits, the pose table and interference policy
  for assemblies (assembly-guide#a0-plan-the-assembly-before-inserting-anything).
Gate D -> M: every requirement has a metric, a limit and a planned check; every planned check
traces to a requirement; open assumptions are listed.

## Stage M: modeling
- One stage per `execute_python` call; feature order: base, main features, patterns, holes and
  fits, fillets and chamfers last (agent-guide).
- Battery V1 after every stage. A finished part: save, close its window (assembly-guide#a1-part-readiness-per-part-before-it-enters-the-assembly).
- Assemblies follow assembly-guide A0-A8.
Gate M -> V: the planned geometry exists, each part passed V1, documents saved.

## Stage V: standard batteries
Run the batteries the plan names, in this order. Each produces rows
`check | value | unit | uncertainty | limit | pass` plus a pair or entity list where relevant.
`verify_model` runs V1 or V2 on the active document and returns exactly these rows.

| Battery | When | How | Pass | Typical time |
|---|---|---|---|---|
| V1 part | after each modeling stage and at part completion | `verify_model` (or `report()`) | rebuild_errors 0, solid_bodies as planned, extents and mass within limits, material assigned, named datums present | < 1 min |
| V2 assembly static | after each inserted component and at completion | `verify_model` on the assembly | rebuild/mate errors 0, all components resolved, interference within the allowance with pairs listed, free components match the intended DOF | 1-3 min |
| V3 motion | once per loop for mechanisms | assembly-guide A4/A6 pose table; solver method or geometric method | every pose within the allowance; the control pose fails clearly | 10-20 min |
| V4 strength and heat | when loads or heat are given | design_calculate screening or FEA at 2 x maximum force and heat; joints listed one by one | utilisation <= 1 at the design load, temperature limits met | 10-30 min |
| V5 appearance | at milestones | same view set each loop after parking (iso, front, top, right, sections) | spec criteria for silhouette, proportion, edges, seams | 2-5 min |
| V6 evidence | at the end of a loop | lite: capture + renders + loop report; full: design_capture, design_submit, review packet | evidence matches the saved files | lite 5 min, full 20-40 min |

Lite V6 is the default for exploration and demos; full V6 when the user asks for a review or the
work is a product change (design-review). Never self-record approval.

## Time boxes and stop rules
| Activity | Budget | When exceeded |
|---|---|---|
| One modeling stage | 3 attempts | change the approach (feature type, simpler profile) or ask |
| One mate | 2 attempts | mate to an assembly datum; log ASSEMBLY or TOOL issue |
| Solver motion check | 2 attempts, about 15 min | geometric pose method; log TOOL issue |
| Any single debugging thread | about 20 min | stop, report the evidence and 2-3 options to the user |
| Device call | under 60 s each | split the work; after a timeout check state before re-running |

## Stage T: issue log and routing
Every failed row, every exceeded time box and every surprise becomes one issue:
`id | loop | battery/check | symptom with numbers | class | severity | action | destination | status`

| Class | Meaning | Destination |
|---|---|---|
| SPEC | requirement, load or assumption wrong or missing | D next loop; ask the user when it changes the concept |
| DATA | input missing (load, catalogue part, existing geometry) | D; ask or record an assumption |
| MODEL | geometry differs from the plan | M next loop |
| ASSEMBLY | mate, datum, pose or DOF wrong | M next loop, assembly-guide steps |
| TOOL | SolidWorks API, solver or MCP tool defect | workaround now; pitfall line in the guide or a tool fix in the same loop |
| METHOD | the check itself could not decide | change the battery definition in the same loop |

An issue is closed only by a verification row that passes in a later loop. Open issues carry
into the next loop report; in Design Studio they are the packet `risks` (open, mitigated,
closed) and each loop is a revision whose parent is the previous loop.

## Loop report (fixed format)
1. Loop number, goal and the changes since the last loop (spec delta, model delta).
2. Verification table: all rows of the batteries that ran.
3. Issues: new, still open, closed in this loop (with the closing row).
4. Next loop plan: which issues, which stage, expected checks; at most 3 options for the user.
5. Housekeeping: saved files, closed windows, documents left open.
