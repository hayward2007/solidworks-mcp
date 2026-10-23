---
title: Quantified industrial design review for robot enclosures
tags: aesthetic, silhouette, proportion, seam, cmf, 디자인, 외형, 실루엣, 파팅, 정비
authority: internal_guide
source: repository:docs/design-studio/IMPLEMENTATION_PLAN.md
checked: 2026-10-21
applicability: Proposed review methods and example targets, not universal aesthetic standards
summary: Translate style intent into geometry, comparisons and measurable visual criteria.
---

# Industrial design rules

## Shape grammar
Start with three explicit visual intents, such as calm, precise and serviceable.
Translate each to editable geometry. Example only: one dominant side silhouette,
one front rake angle, two radius families, and a continuous shoulder line aligned
to the service seam. Distinguish structural radii from cosmetic radii. A fillet
radius must also satisfy material/process/clearance constraints.

Define side and front silhouette with dimensioned vertices and tangent points.
Specify the rake from vertical or horizontal, never just "35 degrees". Define
datum and pivot before reporting a protrusion. Measure total envelope including
sensor covers, fasteners and cables; a flush sensor can still move the whole front
edge forward. Report both quantities.

## Example measurable criteria
The following are proposed project targets [assume], not published standards:

| Criterion | Example target | Evaluation |
|---|---|---|
| Intentional seam width | 1.2 +/- 0.15 mm | min/max after worst-case stack; inspect curved regions too |
| Visible fastener rhythm | equal pitch within +/- 0.5 mm | center positions in datum frame; explain interface exceptions |
| Primary:secondary edge radii | 3:1 | list each radius and process feasibility; inspect tangencies |
| Flushness | offset within +/- 0.2 mm | section at all sensor corners, not a hero render |
| Visual continuity | no unintended tangent breaks | native sections/curvature tools plus human view review |
| Apparent bulk | compare projected side/front area | same orthographic scale, identical configuration |

Record lighting, camera projection, focal length and palette for comparisons.
Use shaded neutral orthographic views to judge geometry, then a material render
to judge finish. A material/color change alone is not a geometric alternative.

## CMF and service surfaces
Specify material grade, finish process, gloss/texture reference, coating thickness
at fits, fingerprint/cleaning considerations and color identifier if approved.
Until a CI reference is supplied, palette is an explicit proposal. Keep status
lights and labels visible at operating posture. Show panel removal direction,
tool swept volume, captive hardware and cable strain relief in the review.
Check heat flow, RF/optical windows and welding/spatter protection separately;
aesthetic glass, coating or black paint can change functional performance.
