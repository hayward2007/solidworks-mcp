---
title: Standards and source applicability registry
tags: standard, ISO, KS, source, 표준, 설계기준, 근거, 출처
authority: internal_registry
source: https://committee.iso.org/standard/66777.html?browse=tc
checked: 2026-10-21
applicability: Discovery registry; not the licensed normative text or a compliance assessment
summary: Separate verified standard scope, vendor capability, legacy notes and project assumptions.
---

# Standards registry

## Evidence levels
| Source | Verified scope here | Numerical authority |
|---|---|---|
| ISO 1101:2017 official abstract | geometrical tolerancing language/interpretation | no full clauses or tolerance tables imported |
| ISO 286, ISO 273, ISO 2768 in legacy notes | topic references only | values remain unverified until exact edition/table is attached |
| RealSense D455 product page | selected sensor catalogue facts | variant/resolution/conditions must match |
| Protolabs machining toolkit | process considerations for that supplier | no blanket process capability guarantee |
| Prusa modeling guide | FDM modeling considerations | validate actual printer/material/orientation |
| Internal design policies | required workflow and evidence fields | not international standards |
| Worked examples | reproducible assumed scenarios | never product measurement or design approval |

Official scope: [ISO 1101](https://committee.iso.org/standard/66777.html?browse=tc).
We accessed the abstract, not the purchased normative document. Do not invent
clauses, claim compliance, or promote every existing `[std]` tag to verified data.

## Adding a rule to the database
Record rule id; rule text/equation; dimension/unit; numerical value or applicability
range; process/material/loading conditions; standard edition and clause/table OR
catalogue revision/page; artifact hash; verification date; whether primary source
was inspected; license/access limits; and conflict/supersession relation.

If two rules conflict, preserve both records, identify applicability differences
and resolve the engineering choice explicitly. The nearest FTS match is not the
most authoritative rule. A current official source can still be irrelevant to
the material, scale or manufacturing process of the current design.
