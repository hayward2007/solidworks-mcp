---
title: Fasteners and holes
tags: fastener, 체결, bolt, 볼트, screw, 나사, 스크류, thread, 탭, tap, M3, M4, M5, M6, M8, clearance hole, 관통홀, 볼트구멍, counterbore, 카운터보어, 자리파기, torque, 토크, insert, 인서트, dowel, 다웰핀, 핀, nut, 너트, washer, 와셔
summary: Metric thread data, tap drills, ISO 273 clearance holes, ISO 4762 heads and counterbores, engagement, torque, pins and inserts.
---

# Fasteners and holes

## Metric coarse threads (ISO 261/262), tap drill = d - P
| Size | Pitch P | Tap drill | Hex key (ISO 4762) |
|---|---|---|---|
| M2 | 0.4 | 1.6 | 1.5 |
| M2.5 | 0.45 | 2.05 | 2 |
| M3 | 0.5 | 2.5 | 2.5 |
| M4 | 0.7 | 3.3 | 3 |
| M5 | 0.8 | 4.2 | 4 |
| M6 | 1.0 | 5.0 | 5 |
| M8 | 1.25 | 6.8 | 6 |
| M10 | 1.5 | 8.5 | 8 |
| M12 | 1.75 | 10.2 | 10 |

## Clearance holes (ISO 273): fine / medium / coarse
M2 2.2 / 2.4 / 2.6, M2.5 2.7 / 2.9 / 3.1, M3 3.2 / 3.4 / 3.6, M4 4.3 / 4.5 / 4.8, M5 5.3 / 5.5 / 5.8, M6 6.4 / 6.6 / 7.0, M8 8.4 / 9.0 / 10, M10 10.5 / 11 / 12, M12 13 / 13.5 / 14.5.
Default: medium. Fine for precise location without pins; coarse for loose assembly or printed parts.

## Socket head cap screws (ISO 4762) and counterbores
| Size | Head dia dk | Head height k | Counterbore dia x depth (typical) |
|---|---|---|---|
| M3 | 5.5 | 3 | 6.5 x 3.3 |
| M4 | 7 | 4 | 8 x 4.4 |
| M5 | 8.5 | 5 | 9.5 x 5.4 |
| M6 | 10 | 6 | 11 x 6.5 |
| M8 | 13 | 8 | 14 x 8.6 |
| M10 | 16 | 10 | 17.5 x 10.8 |
| M12 | 18 | 12 | 20 x 13 |
Preferred lengths: 4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50 mm (longer in 10 mm steps).

## Thread engagement
- Steel nut or steel part: >= 1 d.
- Aluminium, cast iron: 1.5-2 d (or helical inserts).
- Plastics and printed parts: heat-set or helical inserts; self-tapping into plastic needs >= 2.5 d and a tested hole size.
- Blind tapped hole: drill depth >= thread depth + 3 P (+ drill point); thread depth >= engagement + 1 P.

## Tightening torque (property class 8.8, mu about 0.14, approximate)
M3 1.3 N m, M4 3.0, M5 6.0, M6 10, M8 25, M10 49, M12 85. Into aluminium or with class 12.9 adjust per VDI 2230 or the screw maker; into inserts follow the insert maker.

## Locating pins
- Dowel pins ISO 8734 (hardened, m6): 2, 2.5, 3, 4, 5, 6, 8, 10 mm. Press hole H7 in one part, slip fit (F7/G7 or +0.01-0.02) in the other.
- Use one round hole and one slot (or diamond pin) to avoid over-constraint; pins locate, screws clamp.

## Joint layout defaults
- At least 2 screws per joint; spacing >= 3 d, edge distance >= 1.5 d (metal), >= 2.5 d (plastic).
- Prefer one screw size per assembly to reduce tool changes and part numbers.
