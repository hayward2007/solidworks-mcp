---
title: Product design policy - quality before compression
tags: product, quality, policy, 디자인, 외형, 품질, 설계, 근거
authority: internal_policy
source: repository:docs/design-studio/IMPLEMENTATION_PLAN.md
checked: 2026-10-21
applicability: All Design Studio investigations; project-specific requirements take precedence
summary: A complete design iteration combines evidence, dimensioned geometry, quantified performance and visual review.
---

# Product design policy

## Quality priority
Do not cap a specification at ten lines. Use as much detail, retrieval and imagery
as the decision requires. Start with quality context. Compact mode is optional
after the baseline, constraints and risks are understood. Never trade away a
qualification, failure, tolerance, source locator or uncertainty to save tokens.

Product quality is a review objective, not an automatic certification. A passing
screening calculation or attractive render does not establish fit, durability,
sensor performance, manufacturability or user acceptance.

## Basis and certainty are separate
Every dimension has value, unit, basis, evidence references and rationale.
Basis: req, measured, std, cat, calc, dfm, heur, neutral, assume.
Evidence state: measured, observed, reported, assumed, requirement, catalogue,
standard, simulation, test. A screenshot of someone claiming a measurement is
reported evidence until the actual measurement output and conditions are captured.

A standard number alone is not evidence of a numerical clause. Record edition,
clause/table, source artifact and applicability. A vendor DFM number belongs to
that vendor/process/material, not every manufacturing process. An uncertain
dimension remains a parameter and an explicit risk; more decimal places do not
make it more certain. Do not infer original designer intent from shape alone.

## Two concurrent design tracks
Engineering: interfaces, envelope, mass/CoM, load cases, deflection, tolerance
stack, motion clearance, sensor coverage, manufacturing, service and failure cases.
Appearance: silhouette, visual hierarchy, proportion, surface continuity, edge
families, seam/fastener rhythm, color/material/finish, touch and cleaning.
Each iteration must address both tracks and explain tradeoffs between them.

## Protect and review
Preserve input files and protected interfaces. Record the coordinate system,
configuration, unit conversion, source hash and unsaved state before measuring.
Generate at least three meaningful alternatives including a baseline. Change a
coherent parameter group, recompute affected metrics and export a review packet.
Human review precedes an implementation handoff. Never record the agent's own
approval as a user's decision. Production verification needs native CAD and
physical evidence; software gates never certify production readiness.
