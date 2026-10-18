---
title: Fits and tolerances
tags: fit, fits, 끼워맞춤, tolerance, 공차, ISO 286, H7, h6, g6, k6, p6, n6, IT grade, 공차등급, ISO 2768, 일반공차, clearance, 간극, interference, 억지끼워맞춤, press fit, 압입, sliding, 미끄럼, surface, 표면거칠기, roughness
summary: ISO 286 fit selection with deviation values for common sizes, IT grades, ISO 2768 general tolerances, printed-part allowances, surface roughness.
---

# Fits and tolerances

## Choosing a fit (hole basis H7)
| Fit | Type | Use |
|---|---|---|
| H7/g6 | precise running | rotating or sliding shafts, guides |
| H8/f7 | running | free rotation, looser |
| H7/h6 | locational clearance | parts that slide on assembly, spigots |
| H7/k6 | transition | accurate location, assembly by hand or light press (bearing inner rings) |
| H7/n6 | transition, tight | gears/pulleys on shafts with a key |
| H7/p6 | locational interference | pressed bushings, dowel-like location |
| H7/s6 | medium drive | permanent press fits in steel |

## Deviation values (micrometres)
| Size mm | H7 hole | g6 | h6 | k6 | n6 | p6 |
|---|---|---|---|---|---|---|
| 6-10 | 0/+15 | -5/-14 | 0/-9 | +1/+10 | +10/+19 | +15/+24 |
| 10-18 | 0/+18 | -6/-17 | 0/-11 | +1/+12 | +12/+23 | +18/+29 |
| 18-30 | 0/+21 | -7/-20 | 0/-13 | +2/+15 | +15/+28 | +22/+35 |
| 30-50 | 0/+25 | -9/-25 | 0/-16 | +2/+18 | +17/+33 | +26/+42 |

IT grade widths (um): IT6 9 / 11 / 13 / 16, IT7 15 / 18 / 21 / 25, IT8 22 / 27 / 33 / 39 for 6-10 / 10-18 / 18-30 / 30-50 mm.

## General tolerances ISO 2768 (linear)
| Range mm | f (fine) | m (medium, default) | c (coarse) |
|---|---|---|---|
| 0.5-3 | +-0.05 | +-0.1 | +-0.2 |
| 3-6 | +-0.05 | +-0.1 | +-0.3 |
| 6-30 | +-0.1 | +-0.2 | +-0.5 |
| 30-120 | +-0.15 | +-0.3 | +-0.8 |
| 120-400 | +-0.2 | +-0.5 | +-1.2 |

## Printed parts (FDM, 0.4 mm nozzle; verify with a test print)
- Sliding / rotating clearance: 0.2-0.3 mm per side; loose: 0.4 mm.
- Holes print undersize: +0.1-0.2 mm on diameter, or drill/ream after printing.
- Press fit of a metal pin or bearing: nominal -0.05 to -0.15 mm, depends on material and wall.
- Z (layer) accuracy is the layer height; avoid tight fits across layers.

## Surface roughness (Ra, typical)
- Milled 1.6-3.2 um, fine milled/turned 0.8-1.6, ground 0.2-0.8, reamed 0.8-1.6.
- Bearing seats: Ra 0.8 (shaft), 1.6 (housing). Sliding surfaces: 0.4-0.8.
