---
title: Worked design example - sensor bracket and raked panel
tags: example, bracket, stiffness, raked, design, 설계 예제, 처짐, 브래킷, 역경사, 디자인
authority: example
source: repository:solidworks_mcp/design/example.py
checked: 2026-10-21
applicability: Educational assumed concept only; no physical/native CAD/production verification or user approval
summary: Full numerical iteration, explicit geometry and appearance/manufacturing tradeoffs with preserved assumptions.
---

# Worked sensor-front example

## Load and geometry assumptions
The CLI demo is a hypothetical rectangular bracket plus a separate raked-front
section. Nothing here is a measured dimension of the user's robot. Assumed inputs:
end force 20 N, ideal clamp, length 60 mm, width 25 mm, E=69000 MPa, yield=240 MPa,
density=2700 kg/m3. These material-like values are illustrative, not a catalogue
claim. Holes, real fasteners, local fillets, vibration and joint compliance are absent.

The bracket prism is x=0..L, y=-b/2..b/2, z=-t..0 in X-forward/Y-left/Z-up frame.
Clamp datum A is x=0. Real interfaces and their constraints must replace this
ideal boundary before detail design. An apparent mounting plate is not automatically
an ideal clamp, and calculated beam mass is not total assembly mass.

## Compare and recompute
I=b*t³/12; sigma=6FL/(bt²); delta=FL³/(3EI); mass=rho*Lbt*1e-9 kg.
Assumed requirements: delta<=0.3 mm, sigma<=60 MPa, yield margin>=2.5.

| Alternative | Thickness | Stress | Tip deflection | Beam mass | Interpretation |
|---|---:|---:|---:|---:|---|
| A1 baseline | 3 mm | 32 MPa | 0.371014 mm | 12.15 g | fails displacement goal |
| A2 proposed | 4 mm | 18 MPa | 0.156522 mm | 16.20 g | passes conditional screening |
| A3 stiffer | 5 mm | 11.52 MPa | 0.0801391 mm | 20.25 g | extra mass/bulk needs justification |

The demo stores the actual failed A1 revision, then changes only thickness for A2.
The proposed 4 mm thickness improves displacement by about 57.8% at a 4.05 g mass
increase. The choice still needs appearance, interfaces and manufacturing review.
PASS here means the stated model met the assumed threshold, not product approval.

## Panel, optics and tolerance examples
Assume panel height 150 mm and rake 35 degrees from vertical. Its upper edge moves
105.031 mm forward. A 124 x 26 mm camera box aligned to the panel has full X/Z
projections 92.4214/116.488 mm. These projections are neither camera tip motion about
its center nor protrusion from an unspecified body surface.

Assume optical center height 950 mm, down pitch 35 degrees and vertical FOV 87
degrees. Flat-ground near-ray intersection is 193.280 mm horizontally; slant range
is 969.462 mm. The upper ray points above the horizon, so the optical slice has no
finite far-ground bound. Actual useful range/occlusion/depth quality remain unknown.

Assume seam 1.2 mm and +/-0.15, +/-0.15, +/-0.10 mm independent dimensional limits.
Worst-case bounds are 0.8-1.6 mm; RSS is 0.234521 mm but is not an acceptance proof.
The supplier must substantiate the assumed limits. A measured value of 0.29 mm
with uncertainty +/-0.02 mm fails a <=0.30 mm requirement under worst-case review.

## Appearance, process and learning
Example intent: precise and integrated front plane with serviceable panel split.
Quantify the rake, forward envelope, seam width and flushness before evaluating
the impression. Proposed 6/2 mm radius families and neutral CMF are assumptions;
the schematic does not establish real tangency, optical-window compatibility,
tool access or production finish.

Use the exported packet to review the alternatives and accepted unknowns. After
actual CLI human review, `learn` / `design_learn` records the accepted scenario as
`reviewed_case` with its original evidence and applicability. It does not become
a standard or a validated material table. Revoked/stale cases are excluded from
active RAG; their preserved files remain available as history.
