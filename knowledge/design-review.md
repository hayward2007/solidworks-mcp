---
title: Design review and iteration gate
tags: review, approval, iteration, 디자인, 승인, 검토, 반복, 품질
authority: internal_policy
source: repository:solidworks_mcp/design/engine.py
checked: 2026-10-21
applicability: Concept and detail-stage proposals; human review of exact revisions
summary: Review numerical gates and visual evidence together; approval is bound to a revision and its artifact hashes.
---

# Review gate

## Required packet
1. Purpose and immutable project requirements; baseline artifact ids.
2. Datum origin, right-handed X-forward/Y-left/Z-up frame and mm length convention.
3. Dimension ledger with basis, evidence and rationale, plus protected interfaces.
4. Geometry recipe: profiles/vertices, placements, sections, wall/radius families,
   feature order and measured acceptance conditions, not just style adjectives.
5. Three alternatives with numerical tradeoffs and selection reasoning.
6. Recomputed quantitative checks with margin, source and conditions.
7. Orthographic/section/three-quarter views, same framing for comparisons,
   annotated seams, tool/service paths and sensor/motion keep-outs.
8. Silhouette, proportions, edge hierarchy, seam rhythm, CMF and visual criteria.
9. Material/process, datum strategy, critical tolerances, assembly and service steps.
10. Risks, unresolved assumptions, next validation and changes since the prior revision.

## Automatic gates and their limits
Schema and unit validation reject malformed inputs. Missing references, failed
requirements, unresolved critical risks, weakened brief requirements and missing
detail-stage native evidence block approval. Reported/assumed prose cannot pass a
measurement check. Analytical outputs are recalculated; an agent-supplied PASS is
never accepted. Concept-stage assumptions stay visible and do not become verified
facts after approval. Numerical gates cannot judge styling or prove the truth of
a declared measurement; the human reviewer must inspect actual source artifacts.

## Human review
Use the CLI review command after reading the exact export. Record reviewer,
decision and a substantive note identifying accepted tradeoffs. The latest review
decision controls; request_changes/reject removes handoff availability. A new
revision, modified source bytes, mismatching evidence fingerprint or superseded
revision requires another review. The MCP server has no approval operation.

This is a workflow gate, not a security boundary against an agent with arbitrary
shell/CAD access. The agent must not run the approval CLI on behalf of an absent
user. Existing low-level CAD tools remain available for explicitly authorized work.
