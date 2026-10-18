---
title: Design for manufacturing
tags: dfm, 제조성, 가공, machining, cnc, 밀링, milling, turning, 선반, sheet metal, 판금, bend, 벤딩, injection, 사출, draft, 구배, 3d printing, 3d 프린팅, fdm, sla, sls, overhang, 오버행, wall, 두께, hole, 구멍, drill, 드릴
summary: Process rules for CNC machining, sheet metal, injection moulding and 3D printing (FDM, SLA, SLS).
---

# Design for manufacturing

## CNC milling and turning
- Internal corners: radius >= cutter radius; >= 1 mm generally, >= depth / 6 for deep pockets. Use dog-bone reliefs where a square corner must mate.
- Pocket depth <= 3-4 x cutter diameter; walls >= 1 mm (aluminium), thin walls chatter.
- Holes: standard drill sizes; drilled depth <= 6 d (deeper needs peck drilling or gun drilling); flat-bottom holes only if required.
- Threads: depth 1.5-2 d is enough; leave a run-out; avoid tapping below M2.
- Chamfer or round all external edges (C0.5 default); avoid features that need 5-axis unless required.
- Minimize setups: put features on as few faces as possible.

## Sheet metal
- Inside bend radius >= thickness t (aluminium 5052: >= 1-1.5 t; 6061-T6 cracks, avoid bending).
- Hole edge to bend >= 2.5 t + bend radius; hole edge to part edge >= 1.5-2 t; hole diameter >= t.
- Flange length >= 4 t; add bend reliefs at corners.

## Injection moulding
- Draft 1-2 deg (3 deg on textured faces); uniform wall 1.5-3 mm; ribs 50-60 % of the wall, height <= 3 x wall.
- Avoid undercuts unless slides are acceptable; radius every corner (inner >= 0.5 wall).

## FDM printing (0.4 mm nozzle)
- Walls >= 2 mm for strength (>= 0.8 mm minimum), multiples of the line width.
- Overhangs <= 45 deg without support; bridges <= 10-20 mm; chamfer (not fillet) downward-facing edges.
- Holes undersize by 0.1-0.2 mm; horizontal holes print oval: use teardrop shapes or drill.
- Clearances 0.2-0.4 mm per side; use heat-set inserts for repeated screw assembly.
- Orient so loads run along the layers; Z strength is 50-80 % of XY.

## SLA / SLS / MJF
- SLA: walls >= 0.6-1 mm, drain holes for hollow parts, supports leave marks on downward faces.
- SLS/MJF: walls >= 0.8-1 mm, clearance >= 0.3-0.5 mm, escape holes >= 3.5 mm for powder; no supports needed.
