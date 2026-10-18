---
title: Materials
tags: material, materials, 재료, 소재, aluminium, aluminum, 알루미늄, 6061, 7075, 5052, steel, 강, S45C, SM45C, SCM440, stainless, 스테인리스, SUS304, SUS303, titanium, 티타늄, plastic, 플라스틱, POM, 아세탈, PA, 나일론, PEEK, PLA, PETG, ABS, PA12, 탄소섬유, CF, density, 밀도, yield, 항복강도, modulus, 탄성계수
summary: Typical mechanical properties of common metals and plastics (including 3D printing materials) with selection notes.
---

# Materials

## Metals (typical values)
| Material | E (GPa) | Yield (MPa) | UTS (MPa) | Density (kg/m3) | Notes |
|---|---|---|---|---|---|
| Al 6061-T6 | 69 | 276 | 310 | 2700 | general machined parts, anodizable |
| Al 7075-T6 | 72 | 503 | 572 | 2810 | high strength, robot links, poorer corrosion |
| Al 5052-H32 | 70 | 193 | 228 | 2680 | sheet metal, bends well |
| S45C (KS SM45C), normalized | 205 | >= 345 | >= 570 | 7850 | shafts, gears (can be induction hardened) |
| SCM440, quenched and tempered | 205 | >= 835 | >= 980 | 7850 | high-strength shafts, gears |
| SUS304, annealed | 193 | >= 205 | >= 520 | 7930 | corrosion resistant; SUS303 machines better |
| Ti-6Al-4V | 114 | 880 | 950 | 4430 | strength-to-weight, expensive |
Steel values follow JIS G 4051 / G 4053 minimums; aluminium values are typical for the temper.

## Plastics (typical, vary by grade and moisture)
| Material | E (GPa) | Tensile (MPa) | Density (kg/m3) | Notes |
|---|---|---|---|---|
| POM (acetal) | 2.8-3.1 | 60-70 | 1410 | low friction, gears, bushings |
| PA6 (dry) | 2.5-3.0 | 70-80 | 1130 | tough; loses stiffness when wet |
| PEEK | 3.6 | 95-100 | 1300 | high temperature, expensive |

## 3D printing materials (FDM in-plane XY; Z is weaker)
| Material | E (GPa) | Tensile XY (MPa) | Density (kg/m3) | Notes |
|---|---|---|---|---|
| PLA | 3.0-3.5 | 45-60 | 1240 | stiff, brittle, softens at about 55 C |
| PETG | 2.0 | 45-50 | 1270 | tougher than PLA |
| ABS / ASA | 2.0-2.3 | 35-45 | 1040 | heat to about 90 C, warps |
| PA-CF (carbon-filled nylon) | 4-8 | 60-90 | 1150-1250 | functional robot parts; dry before printing |
| PA12 (SLS/MJF) | 1.7-1.9 | 45-50 | 1010 | isotropic-ish powder bed parts |
Z-direction (across layers) strength is typically 50-80 % of XY: orient layers so the main stress runs along them.

## Selection rules of thumb
- Stiffness-limited parts: choose by E / density (aluminium about equal to steel, much lighter for the same mass-stiffness of bending sections).
- Gears: steel/steel or steel/POM; POM vs POM is quiet but weaker; printed gears for prototypes only.
- Set the material in SolidWorks so `report()` mass is meaningful. Without a material the document density is used: check `density_kg_m3` in the report (imported STEP parts showed 1 kg/m3).
