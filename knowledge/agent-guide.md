---
title: Agent guide - evidence-based product-quality SolidWorks design
tags: agent, guide, workflow, token, 토큰, 절약, 가이드, 워크플로, text-to-cad, 텍스트 투 캐드, iteration, 반복, 이터레이션, quality, 품질, report, 보고, vague, 모호
authority: internal_guide
checked: 2026-10-21
applicability: Follow product-design-policy for evidence, quality and human-review requirements
summary: Investigate actual geometry, compare justified alternatives, review appearance and quantify each iteration.
---

# Agent guide

## The loop
1. **Investigate and specify fully**: purpose, baseline hashes, datums, protected interfaces, envelope, mating geometry, load cases/motion, process/material, critical tolerances, service and numerical acceptance. Every number gets value/unit/basis/evidence/rationale. Read product-design-policy, design-evidence and design-review; there is no length cap.
2. **Retrieve complete context**: `design_context(query, mode="quality")` provides mandatory policy and full relevant sections with provenance. Legacy `knowledge_search` / `knowledge_get` remain discovery helpers; their old numeric notes are unverified unless original sources are attached.
   - Gears: `gear_design` first (numbers and warnings, no CAD), then `create_gear` (one call per gear or pair, self-checked); see `gear-generators`.
   - Lightweight parts: `topology_optimize` on the design space, `build: true` for the plate, then add interface features; see `topology-optimization`.
3. **Plan the feature order**: base feature -> main features -> patterns/mirrors -> holes and fits -> fillets/chamfers last.
4. **Build one stage per `execute_python` call**, parameters at the top of the script, helpers injected (see below).
5. **Verify every stage**: `report()` inside the script (or `model_report`), actual dimension checks, material/density and adequate visual evidence. Compare silhouette, proportions, seams, radii and CMF alongside numerical criteria.
6. **Fix the first failure only** and re-run that stage. After 3 failed attempts on the same stage, change the approach (different feature type, simpler profile) or ask.
7. **Submit a full proposal and human review packet before design improvement handoff.** Use three meaningful alternatives and quantified deltas. Never self-record the user's approval. Existing separately authorized routine CAD work does not require a new product-design approval flow.

## Understanding vague requests
- Infer intent from context first: open documents, existing sketches and dimensions, previous parts, the product the user works on. Measure existing geometry instead of inventing values.
- Fill gaps with the basis ladder (design-policy). State all assumptions in one compact line and continue; ask only when the answer changes the concept (ratio, envelope, mating standard, process).
- Prefer editing what exists (a dimension, a sketch, a feature parameter) over rebuilding.
- Translate ambiguous size/strength words into proposed quantified targets and declare them assumptions until confirmed. Never treat one safety-factor default as a universal acceptance criterion.

## Context and output rules
- **One script per stage** instead of many small tool calls; every call costs a few hundred tokens of overhead plus its output.
- **Print little**: counts, key values, pass/fail. Never print whole feature trees, point lists, arrays, or tracebacks of known issues.
- **`report()` / `model_report`** (~150-300 tokens) after each stage gives box, volume, mass, body count and rebuild errors.
- **Visual evidence is required for visual decisions**: obtain consistent orthographic, section and three-quarter views at a resolution that reveals the design issue. Image token cost depends on provider and is not measured by this system.
- **Reuse code**: put helper functions and computed geometry in `store` (persists while the server runs) and call them from later, shorter scripts.
- **Use recipes, not trial and error**: `solidworks-api` lists calls and argument lists that are known to work.
- **Don't repeat context**: do not re-read knowledge sections or files already in the conversation.
- **Quality before compression**: avoid irrelevant repeated output, but retain dimensions, sources, failures, uncertainty and visual tradeoffs in the review packet. Compact retrieval is optional.

## Quality gate (every stage)
- `report()["errors"]` is empty (rebuild OK).
- Body count is as intended (usually 1 solid body per part).
- Box and key dimensions match the spec (modeled values exact; tolerances belong to drawings).
- Mass and center of mass are plausible for the material (density check).
- Assemblies: `check_interference` total is 0 (or only intended press fits), mates have no errors, free motion is what was asked for.
- Manufacturability: walls, radii, clearances, hole depths meet `dfm` for the chosen process.
- Every key dimension has a basis tag; untagged numbers are bugs.

## execute_python helpers
Injected names: `val`, `call`, `arr`, `strings`, `byref_int`, `byref_bool`, `select`, `plane`, `feats`, `feat`, `active`, `report`, `render`, `store`, `mm`, `deg`, plus `sw`, `doc`, `automation`, `math`, `json`.
- Units in the API are metres and radians: multiply mm values by `mm`, degrees by `deg`.
- `plane("front")` returns the localized default plane name ("정면" in Korean SolidWorks).
- `report()` returns the compact model report; `render("iso")` or `render(("iso", "front"))` attaches a small image to the tool result.
- `store` is a dict kept between calls.

```python
P = dict(w=60.0, h=40.0, t=8.0, hole=6.6)   # w,h [req]; t [neutral R10]; hole M6 clearance [std ISO 273]
sm = doc.SketchManager
select(doc, plane("top"), "PLANE"); call(sm, "InsertSketch", True)
call(sm, "CreateCenterRectangle", 0, 0, 0, P["w"] / 2 * mm, P["h"] / 2 * mm, 0)
call(sm, "InsertSketch", True)
# ... extrude, holes ...
result = report()
```

## Reporting format
1. One-line spec and assumptions.
2. Table of key parameters: value, unit, basis tag.
3. Verification numbers: box, mass, errors, interference.
4. Open issues and at most 3 next options.
