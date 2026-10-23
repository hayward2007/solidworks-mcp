---
title: Mechanical reverse engineering investigation playbook
tags: reverse engineering, inspect, mesh, solidworks, 역설계, 리버스, 실측, 형상
authority: internal_guide
source: https://rea.tools/
checked: 2026-10-21
applicability: Workflow analogy only; mechanical method below is an original internal procedure
summary: Inspect the artifact, preserve observations, reconstruct constraints, compare hypotheses and validate a new design.
---

# Reverse engineering investigation

## Investigation sequence
REA's software workflow motivates inspect -> evidence -> explain -> change.
This system applies that interaction to mechanical artifacts without depending on
REA or claiming CAD intent recovery. Start with one falsifiable question, e.g.
"Can the camera be flush in the front face while keeping the hip interface and
increasing forward envelope by less than the project limit?"

1. Import baseline assembly, drawing, images and supplier data as separate artifacts.
2. Capture native report and feature/dimension data on the Windows SolidWorks host.
3. Build an interface map: datum A mounting plane, B primary axis, C locating feature;
   list fastener centers, mating surfaces, connector/access corridors and motion volumes.
4. Segment observations into functional zones: structure, skin, sensor aperture,
   joint transition, maintenance panel, cooling and cable routing.
5. Write competing intent hypotheses. A circular face might be a bearing seat,
   tool-access plug or styling detail. Resolve with mating geometry/drawings/tests.
6. Reconstruct a parametric design with a dimension ledger. Mark unconstrained
   parameters and uncertainty; original feature sequence is usually unknowable.
7. Compare three alternatives under identical interfaces, camera and metrics.
8. Review dimensions and appearance, then implement in a preserved CAD copy.

## Native and portable inspection
Native snapshot: title/path/configuration context, saved-file hash, unsaved flag,
reported rebuild errors, bodies/mass/box, feature identities and display dimension
SI values. Suppressed features, nested parts, drawing tolerances and complex
surfaces require deeper inspection through existing tools. Never silently ignore
an extraction failure.

STL inspection requires an explicit unit. It returns bounding box, triangle area,
edge closure, winding and provisional signed-volume magnitude. Tessellation is not
an exact B-rep and cannot establish hole fit, material or G1/G2 continuity. STEP,
SLDPRT and SLDASM remain original artifacts; open a copy on Windows and capture
native data. The portable server does not pretend to parse those formats.

## Reconstruction deliverables
Keep observation and hypothesis tables, entity/frame map, parameter/evidence
ledger, manufacturing hypotheses, visual language rules, alternative comparison,
verification plan and known coverage limits. Import a licensed full standard or
catalogue excerpt only when available; do not fabricate missing tables.
