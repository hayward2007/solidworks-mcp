---
title: Bearings
tags: bearing, bearings, 베어링, ball bearing, 볼베어링, deep groove, 깊은홈, 6000, 6200, 6800, 6900, angular contact, 앵귤러, crossed roller, 크로스롤러, needle, 니들, thrust, 스러스트, life, 수명, L10, fit, 끼워맞춤, shoulder, 숄더, preload, 예압
summary: Bearing type selection, standard deep-groove dimensions (ISO 15), L10 life, fits, shoulders and mounting rules.
---

# Bearings

## Choosing a bearing type
| Need | Type | Notes |
|---|---|---|
| General radial load, moderate axial | deep groove ball (60xx, 62xx, 68xx, 69xx) | cheapest, sealed versions (ZZ, 2RS) |
| Combined radial + axial, stiffness | angular contact (70xx, 72xx) in pairs | back-to-back (DB) for moment stiffness |
| Moment loads in a thin space (robot joints) | crossed roller | one bearing carries radial, axial and moment loads |
| Large bore, small section | thin-section (constant section) | light, for hollow joints |
| High radial load, small section | needle roller | needs a hardened shaft or inner ring |
| Pure axial | thrust ball | no radial capacity |
| Misalignment | self-aligning ball / spherical roller | |

## Deep groove ball bearings (ISO 15), d x D x B in mm
| Bore | 68xx (thin) | 69xx | 60xx | 62xx |
|---|---|---|---|---|
| 10 | 6800: 10x19x5 | 6900: 10x22x6 | 6000: 10x26x8 | 6200: 10x30x9 |
| 12 | 6801: 12x21x5 | 6901: 12x24x6 | 6001: 12x28x8 | 6201: 12x32x10 |
| 15 | 6802: 15x24x5 | 6902: 15x28x7 | 6002: 15x32x9 | 6202: 15x35x11 |
| 17 | 6803: 17x26x5 | 6903: 17x30x7 | 6003: 17x35x10 | 6203: 17x40x12 |
| 20 | 6804: 20x32x7 | 6904: 20x37x9 | 6004: 20x42x12 | 6204: 20x47x14 |
| 25 | 6805: 25x37x7 | 6905: 25x42x9 | 6005: 25x47x12 | 6205: 25x52x15 |
| 30 | 6806: 30x42x7 | 6906: 30x47x9 | 6006: 30x55x13 | 6206: 30x62x16 |
| 35 | | | 6007: 35x62x14 | |
| 40 | | | 6008: 40x68x15 | |

Small sizes: 625 5x16x5, 626 6x19x6, 608 8x22x7, 688 8x16x5, 695 5x13x4, 696 6x15x5.
Load ratings (C, C0) and limiting speeds differ by maker: take them from the catalogue of the bearing you buy.

## Life
- Basic rating life L10 = (C / P)^p million revolutions, p = 3 for ball, 10/3 for roller bearings.
- In hours: L10h = 10^6 / (60 n) x L10, n in rpm.
- Equivalent load P = X Fr + Y Fa (X, Y from the catalogue; for small axial load P = Fr).
- Targets: intermittent use 4,000-8,000 h, 8 h/day machines 20,000-30,000 h.

## Fits (ISO 286)
| Situation | Shaft | Housing |
|---|---|---|
| Rotating inner ring, normal load | k5 / k6 (j6 light) | H7 |
| Rotating outer ring (e.g. wheel hub) | g6 / h6 | N7 / P7 |
| Light load, easy assembly, small bearings | h5 / j5 | H7 / J7 |
| Printed housings (FDM) | | nominal D - 0.05 to -0.1 mm, test print first |
The ring that rotates relative to the load gets the interference fit; the other ring may slide.

## Shoulders and mounting
- Use the catalogue abutment dimensions (da min, Da max). Rule of thumb: shoulder height about 1/3 to 1/2 of the ring cross-section height (D - d) / 2, never touching the seal or cage.
- Shoulder fillet radius must be smaller than the bearing chamfer rs.
- Locate one bearing axially on both rings (fixed), let the other float axially (thermal growth).
- Axial retention: shoulder + retaining ring (DIN 471/472), nut, or clamping cover.
- Angular contact / crossed roller: design for the preload the maker specifies; DB arrangement for tilting stiffness.

## Robot-joint notes
- Output bearings of a joint carry the moment from the link: crossed roller or a DB pair of angular contact bearings spaced as far apart as the envelope allows.
- Thin series (68xx, 69xx) keep hollow shafts large for cables.
