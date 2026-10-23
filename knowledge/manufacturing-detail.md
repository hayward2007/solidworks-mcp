---
title: Manufacturing, tolerance and assembly detail checklist
tags: dfm, machining, fdm, tolerance, assembly, 가공, 공차, 조립, 정비, 프린팅
authority: internal_guide
source: https://www.protolabs.com/en-gb/resources/design-for-machining-toolkit/
checked: 2026-10-21
applicability: Vendor guidance informs process questions; internal numeric examples below are assumptions
summary: Turn manufacturability into process-specific dimensions, tolerance stacks and supplier questions.
---

# Manufacturing detail

## Process-specific decisions
For milling, select stock/orientation, clamp surfaces, cutter diameter/reach,
accessible pocket directions and a deburr strategy. Internal corner radii follow
tool access; deepen a pocket only after checking tool stiffness and chip removal.
Ask the intended supplier to confirm the tolerance and finish, rather than assigning
a universal wall minimum. Protolabs describes cutter-induced internal radii and
thin-feature limitations for its own process, not every factory.

For FDM, record printer/nozzle, material, moisture, layer height, orientation,
perimeters, infill and postprocess. Calibrate holes and sliding clearances with a
coupon made in the same configuration. Prusa's guide likewise emphasizes print
orientation and process-aware modeling. SLA/SLS/MJF/FDM numbers are not interchangeable.
Source: [Prusa modeling guide](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135).

## Tolerance example and datum scheme
Example proposed seam: nominal gap 1.2 mm, shell A +/-0.15 mm, shell B +/-0.15 mm,
alignment +/-0.10 mm. Worst-case gap is 0.80-1.60 mm. This is a calculated result
for assumed inputs, not a process capability statement. RSS = 0.2345 mm is only
informative unless independence, distribution and assembly centering are justified.

Datum A = mounting plane; B = primary locating axis/edge; C = clocking feature.
Explain how each locating constraint is created and inspected. Do not constrain
every screw as a tight locating pin. Assign critical hole positions, shaft/bore
fits, flatness and panel flushness individually; general tolerances do not replace
functional stacks. Budget coating, thermal growth, compliance and wear explicitly.

## Assembly and service
Write a numbered build sequence with hardware, tool approach, torque source,
access and inspection at each step. Verify inserts, thread engagement, edge
distance, bearing shoulders and connector unmating paths from selected catalogues.
Proposed torque and engagement rules remain assumptions until supported by the
actual fastener/material combination. Show how a failed sensor can be removed
without disturbing protected interfaces. Record manufacturing questions as risks,
then close them with supplier evidence or tests.
