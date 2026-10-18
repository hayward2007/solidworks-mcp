---
title: Shafts, keys and axial retention
tags: shaft, 축, 샤프트, key, 키, keyway, 키홈, DIN 6885, KS B 1311, torsion, 비틀림, bending, 굽힘, retaining ring, 스냅링, 리테이닝링, circlip, DIN 471, DIN 472, d-cut, 디컷, set screw, 무두볼트, deflection, 처짐
summary: Shaft sizing formulas, deflection limits, parallel key dimensions (DIN 6885 / KS B 1311), retaining ring grooves, D-cuts and set screws.
---

# Shafts, keys and axial retention

## Sizing a solid shaft
- Torsion only: tau = 16 T / (pi d^3) -> d = (16 T / (pi tau_allow))^(1/3).
- Bending + torsion (von Mises): sigma_e = 32 / (pi d^3) x sqrt(M^2 + 0.75 T^2) <= sigma_y / SF.
- Hollow shaft: replace d^3 with (D^4 - d_i^4) / D.
- Keyways, grooves and shoulders are stress raisers: use Kt about 2 for a keyway, 2-3 for a sharp shoulder; add a fillet r >= 0.1 d.

## Stiffness limits (heuristic)
- Slope at deep groove ball bearings <= 0.001 rad (cylindrical roller 0.0005).
- Deflection at a gear <= 0.01 m (module); torsional twist of precise drives <= 0.25 deg/m.

## Parallel keys (DIN 6885-1, KS B 1311): key b x h, shaft groove depth t1, hub groove depth t2
| Shaft d | b x h | t1 | t2 |
|---|---|---|---|
| over 6 to 8 | 2 x 2 | 1.2 | 1.0 |
| 8-10 | 3 x 3 | 1.8 | 1.4 |
| 10-12 | 4 x 4 | 2.5 | 1.8 |
| 12-17 | 5 x 5 | 3.0 | 2.3 |
| 17-22 | 6 x 6 | 3.5 | 2.8 |
| 22-30 | 8 x 7 | 4.0 | 3.3 |
| 30-38 | 10 x 8 | 5.0 | 3.3 |
| 38-44 | 12 x 8 | 5.0 | 3.3 |
| 44-50 | 14 x 9 | 5.5 | 3.8 |
Key length about 1-1.5 d. Key shear: tau = 2 T / (d b L); key bearing pressure p = 4 T / (d h L) (approx.), keep p below about 100 MPa for steel hubs.

## External retaining rings (DIN 471): shaft d -> groove diameter x width
d 10 -> 9.6 x 1.1, 12 -> 11.5 x 1.1, 15 -> 14.3 x 1.1, 20 -> 19.0 x 1.3, 25 -> 23.9 x 1.3, 30 -> 28.6 x 1.6.
Internal rings (DIN 472) follow the same idea in bores; take groove data from the ring maker.

## Small shafts in robots and prototypes
- D-cut: flat depth about 0.1 d, length >= hub length; transmits moderate torque with a set screw.
- Set screws: cup point on a flat, size about d/4 (M3 on 8-12 mm shafts, M4 on 12-16 mm).
- Prefer keyless clamping hubs or splines for reversing loads (keys fret under reversal).
