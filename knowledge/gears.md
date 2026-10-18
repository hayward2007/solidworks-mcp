---
title: Gears
tags: gear, gears, 기어, 치차, spur, 스퍼, helical, 헬리컬, bevel, 베벨, spiral bevel, 스파이럴, 스파이럴 베벨, miter, 마이터, worm, 웜, planetary, 유성, 유성기어, harmonic, 하모닉, strain wave, cycloidal, 사이클로이드, module, 모듈, pressure angle, 압력각, backlash, 백래시, involute, 인볼류트, rack, 랙, tooth, 잇수
summary: Gear type selection, geometry formulas (spur, helical, bevel, spiral bevel, worm, planetary), strength quick checks, verified SolidWorks recipes and mesh checks.
---

# Gears

Generators: `gear_design` / `create_gear` build all types below except strain wave and cycloidal (see gear-generators).

## Choosing a gear type
| Need | Type | Typical ratio per stage | Notes |
|---|---|---|---|
| Parallel shafts, simple | spur | 1-6 | 98-99 % efficient, no axial load |
| Parallel shafts, quiet or strong | helical | 1-8 | axial thrust Fa = Ft tan(beta), beta 15-30 deg |
| Intersecting shafts | straight / spiral bevel | 1-5 | spiral: smoother, stronger, thrust depends on hand |
| 90 deg turn, same speed | miter (bevel 1:1) | 1 | pitch angle 45 deg on both |
| Crossed shafts, high ratio | worm | 5-100 | low efficiency, may self-lock |
| Coaxial, compact | planetary | 3-10 | load sharing over N planets |
| Very high ratio, near-zero backlash | strain wave (harmonic) | 30-160 | buy as a unit |
| High ratio, shock tolerant | cycloidal | 10-100 | common in robot joints |

## Standard parameters
- Modules, ISO 54 first choice: 0.5, 0.6, 0.8, 1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10. Second choice: 0.55, 0.7, 0.9, 1.125, 1.375, 1.75, 2.25, 2.75, 3.5, 4.5, 5.5, 7, 9.
- Basic rack ISO 53: pressure angle 20 deg, addendum 1.0 m, dedendum 1.25 m, root fillet about 0.38 m.
- Undercut limit (20 deg, no profile shift): z_min = 2 / sin^2(alpha) = 17 (14 tolerable). For fewer teeth use profile shift x = (17 - z) / 17.

## Spur gears
- d = m z, da = d + 2 m (1 + x), df = d - 2.5 m + 2 x m, db = d cos(alpha), circular pitch p = pi m.
- Tooth thickness at the pitch circle s = pi m / 2 + 2 x m tan(alpha).
- Centre distance a = m (z1 + z2) / 2 (no shift). Transverse contact ratio: aim 1.4-1.8, never below 1.2.
- Backlash: total circumferential backlash about 0.04 m for machined gears (0.03-0.08 mm at m 1), each gear thinned by half; 0.1-0.2 mm total for FDM gears.
- Hunting tooth: choose z1, z2 without common factors when wear matters.

## Helical gears
- Normal module mn is the standard one; transverse mt = mn / cos(beta); d = mt z.
- alpha_t = atan(tan(alpha_n) / cos(beta)); axial pitch px = pi mn / sin(beta).
- Overlap ratio eps_beta = b sin(beta) / (pi mn) >= 1 recommended.
- External mesh on parallel shafts: opposite hands. Axial force Fa = Ft tan(beta).

## Straight bevel gears
- Pitch angles (shaft angle Sigma): tan(delta1) = sin(Sigma) / (z2/z1 + cos(Sigma)); for Sigma = 90 deg tan(delta1) = z1/z2, delta2 = 90 - delta1.
- Outer (heel) pitch diameter de = m z with m the outer transverse module; outer cone distance Re = de / (2 sin(delta)).
- Face width b <= Re/3 and <= 10 m (AGMA). Tooth depth tapers toward the apex (addendum and dedendum proportional to cone distance).
- Tooth shape: Tredgold approximation, an equivalent spur gear on the back cone with zv = z / cos(delta) and rv = r / cos(delta).
- Both pitch-cone apexes must coincide in the assembly; axial mounting error changes backlash and contact.

## Spiral bevel gears
- Mean spiral angle beta_m usually 35 deg (Gleason), range 20-40 deg; zerol = 0 deg.
- **A pair needs opposite hands.** Two copies of the same part never mesh (measured for a 20T m2 miter pair: 75-84 mm3 interference at every phase; opposite hand at half-pitch phase: 0.58 mm3).
- Hand: looking at the tooth side (from the apex), right hand = the outer half of a tooth is inclined clockwise.
- Tooth trace: circular arc of the face-mill cutter radius rc in the developed pitch-cone (crown) plane. rc between Rm and 1.2 Rm keeps the spiral-angle variation moderate (Rm 21.2 mm, rc 25.4 mm: 30.8 deg toe, 35 deg mean, 42.4 deg heel).
- Transverse pressure angle alpha_t = atan(tan(alpha_n) / cos(beta)), about 24 deg at 35 deg with alpha_n 20 deg.
- Face width <= 0.3 Re; wide faces increase the spiral-angle variation and weaken the toe.
- Thrust: choose hand and rotation so the pinion is pushed out of mesh (away from the apex) under drive torque.

## Spiral bevel: verified SolidWorks recipe
1. Revolve the blank: front cone (normal to the pitch cone at the toe), face (tip) cone, back cone (normal at the heel), flat faces. All cones share the pitch apex (converging depth). Put the apex at the part origin, axis = X.
2. One tooth space = loft cut through 7-9 transverse sections (Tredgold involute, scaled by cone distance, rotated by the spiral angle phi(R)), extended 1-2 mm beyond toe and heel.
3. Add 4 guide curves through the matching corners of every section (root and top, both flanks). Without guides the loft matched the wrong vertices and produced wavy bulges.
4. Circular-pattern the cut z times about the gear axis.
5. Opposite hand in the same file: configuration "LH" = mirror body about a plane containing the axis + delete the original body; suppress both features in the default configuration.
6. Mesh check: mate apex to apex, axes perpendicular, rotate the mate by half a pitch (180/z deg), interference about 0.
7. Assembly: coincident apex points, perpendicular axes, set the half-pitch phase, then a Gear mate z1:z2. An orbiting gear rolls correctly around a fixed one (measured: spin = orbit angle for 1:1).

## Worm gears
- Axial module m of the worm = transverse module of the wheel; diameter quotient q = d1 / m (8-20 typical).
- Worm and wheel have the same hand (a right-hand worm drives a right-hand wheel).
- Lead angle gamma: tan(gamma) = z1 m / d1 = z1 / q. Centre distance a = m (q + z2) / 2.
- Efficiency (worm driving) about tan(gamma) / tan(gamma + phi'), phi' = atan(mu / cos(alpha_n)).
- Self-locking only if gamma < phi' (roughly < 3-5 deg for lubricated steel/bronze); vibration can still back-drive it, so use a brake where safety matters.
- Materials: hardened steel worm with bronze (CuSn12) or POM wheel.

## Planetary gear sets
- Ratio with ring fixed, sun input, carrier output: i = 1 + Zr / Zs.
- Concentricity (same module, no shift): Zr = Zs + 2 Zp.
- Equal-spacing assembly condition: (Zs + Zr) / N must be an integer (N planets).
- Neighbour clearance: (Zs + Zp) sin(pi / N) > Zp + 2 (in module units).
- 3 planets give statically determinate load sharing; more planets need floating or tight tolerances.

## Strain wave and cycloidal drives
- Strain wave: flexspline has 2 fewer teeth than the circular spline; ratio = Zf / (Zc - Zf), e.g. 160/162 -> 80:1. Buy complete units (Harmonic Drive CSF/SHF and equivalents).
- Cycloidal: N pins, N - 1 lobes -> ratio N - 1 with the pins fixed. Key parameters: pin circle radius, pin radius, eccentricity e. Two discs 180 deg apart balance the mass.

## Strength quick check (Lewis)
- Tangential force Ft = 2 T / d. Bending stress sigma = Ft / (b m Y).
- Lewis form factor Y (20 deg full depth): z12 0.245, 15 0.290, 17 0.303, 20 0.322, 24 0.337, 30 0.359, 40 0.389, 50 0.409, 75 0.435, 100 0.447, rack 0.485.
- Allowable bending stress (with margin, slow speed), heuristic: through-hardened steel 150-250 MPa, POM 20-30 MPa, PA 20-25 MPa, FDM PLA/PETG 8-15 MPa, PA-CF 20-30 MPa.
- For final designs use ISO 6336 / AGMA 2001 (bending and pitting).

## Accuracy and backlash
- ISO 1328 grades: 5-7 ground/precision, 8-9 hobbed, 10-12 printed or moulded.
- Typical backlash (machined): 0.03-0.08 mm for m 1, 0.05-0.12 mm for m 2.

## Modeling checks
- Measure tip and root diameters, face width, mass; count teeth from the pattern.
- Mesh: place the mating gear at the theoretical centre distance (or common apex), check interference at 2-3 phases within one pitch.
- Same-hand check for helical, spiral bevel and worm pairs before anything else.
