---
title: Agent guide - fast, token-efficient SolidWorks design
tags: agent, guide, workflow, token, 토큰, 절약, 가이드, 워크플로, text-to-cad, 텍스트 투 캐드, iteration, 반복, 이터레이션, quality, 품질, report, 보고, vague, 모호
summary: How to turn short or vague requests into verified SolidWorks models in few calls and few tokens.
---

# Agent guide

## The loop
1. **Spec** (max ~10 lines): purpose, envelope, interfaces (mating parts, shafts, bolt patterns), loads/motion, process + material, the numbers to hit. Every number gets a basis tag ([req] [std] [calc] [cat] [dfm] [heur] [neutral], see design-policy).
2. **Look up only what you need**: `knowledge_search` (snippets, cheap) then `knowledge_get` for one section. Proven API recipes are in `solidworks-api`.
3. **Plan the feature order**: base feature -> main features -> patterns/mirrors -> holes and fits -> fillets/chamfers last.
4. **Build one stage per `execute_python` call**, parameters at the top of the script, helpers injected (see below).
5. **Verify every stage**: `report()` inside the script (or `model_report`). Images only at milestones.
6. **Fix the first failure only** and re-run that stage. After 3 failed attempts on the same stage, change the approach (different feature type, simpler profile) or ask.
7. **Quality gate, then a short report.**

## Understanding vague requests
- Infer intent from context first: open documents, existing sketches and dimensions, previous parts, the product the user works on. Measure existing geometry instead of inventing values.
- Fill gaps with the basis ladder (design-policy). State all assumptions in one compact line and continue; ask only when the answer changes the concept (ratio, envelope, mating standard, process).
- Prefer editing what exists (a dimension, a sketch, a feature parameter) over rebuilding.
- Ambiguous size words: "small" = fits the stated envelope with the minimum standard part; "strong" = safety factor 3 on yield; "light" = remove material only where stress allows (pockets, lightening holes) and report mass.

## Token budget rules
- **One script per stage** instead of many small tool calls; every call costs a few hundred tokens of overhead plus its output.
- **Print little**: counts, key values, pass/fail. Never print whole feature trees, point lists, arrays, or tracebacks of known issues.
- **`report()` / `model_report`** (~150-300 tokens) after each stage gives box, volume, mass, body count and rebuild errors.
- **Images are expensive but decisive**: one view at size 384 is about 200 tokens, the 2x2 grid at 384 about 800. Use them after the base shape, after patterns, and at the end, or whenever a number looks wrong. Never send full screenshots.
- **Reuse code**: put helper functions and computed geometry in `store` (persists while the server runs) and call them from later, shorter scripts.
- **Use recipes, not trial and error**: `solidworks-api` lists calls and argument lists that are known to work.
- **Don't repeat context**: do not re-read knowledge sections or files already in the conversation.
- **Short answers**: what was built, key dimensions with their basis, check results, at most 3 next options.

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
