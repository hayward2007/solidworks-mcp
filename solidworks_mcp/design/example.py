"""Complete reproducible educational iteration. No product/CAD measurements are fabricated."""
from copy import deepcopy
from pathlib import Path
from .common import encoded, write_new
from .engine import Engine
from .report import export_review


def example_brief():
    def req(rid, metric, unit, op, limit, rationale):
        return {"id": rid, "metric": metric, "unit": unit, "operator": op, "limit": limit,
                "tolerance": 0, "critical": True, "rationale": rationale}
    return {"title": "센서 전면 모듈 · 수치와 외형 동시 검토 예제", "purpose": "Educational assumed sensor-panel and bracket scenario; not a Walker product redesign or measured production design.",
            "requirements": [req("R1", "deflection", "mm", "le", 0.3, "Assumed optical alignment budget for this example"),
                             req("R2", "stress", "MPa", "le", 60, "Assumed screening stress bound, not fatigue acceptance"),
                             req("R3", "factor", "1", "ge", 2.5, "Assumed minimum yield margin"),
                             req("R4", "near_ground", "mm", "le", 350, "Assumed geometric ground-view goal"),
                             req("R5", "overhang", "mm", "le", 110, "Assumed forward envelope allowance"),
                             req("R6", "minimum_gap", "mm", "ge", 0.4, "Assumed no-contact seam margin")]}


def schematic():
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="600" viewBox="0 0 1100 600">
<rect width="1100" height="600" fill="#f4f5ef"/><g font-family="sans-serif" fill="#173e35">
<text x="40" y="48" font-size="25" font-weight="bold">SENSOR FRONT / ASSUMED CONCEPT STUDY</text>
<text x="40" y="78" font-size="14">Dimensioned side-section schematic · not CAD, ray tracing, or a product measurement</text>
<g stroke="#365e50" stroke-width="2"><path d="M120 420 L120 150 L309 150 L120 420" fill="#d4dfd4"/>
<path d="M309 150 L365 150 L176 420 L120 420" fill="#527365"/>
<path d="M288 180 L249.66 153.16 L121.64 336.01 L159.98 362.85Z" fill="#202d32"/>
<path d="M120 450H309M120 440V460M309 440V460" fill="none"/>
<path d="M80 150V420M70 150H90M70 420H90" fill="none"/>
<path d="M440 430H820V454H440ZM440 454V485H460V454" fill="#527365"/>
<path d="M460 515H820M460 505V525M820 505V525" fill="none"/>
<path d="M820 360V420M810 405L820 420L830 405" fill="none"/>
</g><text x="144" y="480" font-size="15">H tan(35°) = 105.031 mm</text>
<text x="35" y="300" font-size="14" transform="rotate(-90 35 300)">H = 150 mm</text>
<text x="194" y="130" font-size="16">35° rake from vertical</text>
<text x="420" y="335" font-size="20" font-weight="bold">Bracket / cantilever screening</text>
<text x="805" y="345" font-size="15">20 N</text><text x="600" y="540" font-size="15">L = 60 mm</text>
<text x="500" y="480" font-size="14">width 25 mm · proposed thickness 4 mm</text>
<text x="440" y="568" font-size="14">t=3: δ 0.3710 mm FAIL · t=4: δ 0.1565 mm PASS · t=5: δ 0.0801 mm</text>
<text x="40" y="560" font-size="13">No depth-valid coverage / collision / manufacturing claim</text>
<text x="40" y="580" font-size="13">X forward → · Z up ↑ · assumed ideal clamp</text></g></svg>'''


def make_example(store, project, output):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("demo output already exists; choose a new directory")
    output.mkdir(parents=True)
    created = store.create_project(project, example_brief())
    eid = created["brief_evidence_id"]
    source = output / "assumed-scenario.json"
    write_new(source, (encoded({"kind": "educational assumption", "E_mpa": 69000, "yield_mpa": 240, "density_kg_m3": 2700,
                               "note": "Illustrative material inputs, not a verified catalogue or product measurement"}) + "\n").encode())
    aid = store.import_artifact(project, source)["id"]
    assumed = store.add_evidence(project, "assumed", "All dimensions and material/load inputs are an educational scenario.", [aid],
                                 "assumed-scenario.json; no physical or CAD validation")
    drawing = output / "concept-section.svg"
    write_new(drawing, schematic().encode())
    visual = store.import_artifact(project, drawing)["id"]
    view_ev = store.add_evidence(project, "observed", "Original schematic illustrates proposed sections, datums and alternative thicknesses.", [visual],
                                 "concept-section.svg; side view; illustrative, not native CAD")
    raw = {"force": (20, "N"), "length": (60, "mm"), "width": (25, "mm"), "thickness": (3, "mm"),
           "E": (69000, "MPa"), "yield": (240, "MPa"), "density": (2700, "kg/m3"), "camera_height": (950, "mm"),
           "pitch": (35, "deg"), "vfov": (87, "deg"), "min_range": (600, "mm"), "panel_height": (150, "mm"),
           "rake": (35, "deg"), "camera_length": (124, "mm"), "camera_depth": (26, "mm"),
           "gap": (1.2, "mm"), "tol_a": (0.15, "mm"), "tol_b": (0.15, "mm"), "tol_alignment": (0.1, "mm")}
    params = [{"id": name, "value": value, "unit": unit, "basis": "assume", "evidence_ids": [assumed["id"]],
               "rationale": "Explicit example input; replace with a measured interface, project requirement or exact catalogue source."} for name, (value, unit) in raw.items()]
    calculations = [{"id": "C1", "kind": "cantilever", "inputs": {"force_n": "force", "length_mm": "length", "width_mm": "width", "thickness_mm": "thickness", "elastic_modulus_mpa": "E", "yield_mpa": "yield", "density_kg_m3": "density"}, "purpose": "Screen bracket stiffness and yield margin; exclude mounting-joint compliance"},
                    {"id": "C2", "kind": "camera_ground", "inputs": {"height_mm": "camera_height", "down_pitch_deg": "pitch", "vertical_fov_deg": "vfov", "min_range_mm": "min_range"}, "purpose": "Geometric flat-ground slice only; no occluders or sensor performance claim"},
                    {"id": "C3", "kind": "raked_panel", "inputs": {"height_mm": "panel_height", "rake_deg": "rake", "camera_length_mm": "camera_length", "camera_depth_mm": "camera_depth"}, "purpose": "Quantify panel overhang and full camera-box projection"},
                    {"id": "C4", "kind": "tolerance_stack", "inputs": {"gap_mm": "gap", "part_a_tol_mm": "tol_a", "part_b_tol_mm": "tol_b", "alignment_tol_mm": "tol_alignment"}, "purpose": "Worst-case seam gap; no statistical distribution assumed"}]
    packet = {"schema_version": 1, "title": example_brief()["title"], "summary": "Improve an illustrative camera bracket from 3 to 4 mm while retaining a 35-degree raked-panel concept. All inputs are explicitly assumed.",
              "stage": "concept", "usage": "example", "baseline_artifact_ids": [created["brief_artifact_id"], aid],
              "datums": {"origin": "Example bracket clamp center at mounting face A", "axes": "X forward, Y left, Z up", "length_unit": "mm"},
              "parameters": params,
              "geometry": [{"id": "G1", "type": "Rectangular bracket screening beam", "parameter_ids": ["length", "width", "thickness"], "frame": "Clamp x=0; free end x=60; centered in Y; top at Z=0", "construction": "Sketch rectangle x=0..length, y=-width/2..width/2. Extrude down by thickness; holes and local fillets excluded from analytical model.", "acceptance": "Confirm prism dimensions in native CAD, then model real joints/holes before detail-stage release."},
                           {"id": "G2", "type": "Raked panel side section", "parameter_ids": ["panel_height", "rake", "camera_length", "camera_depth"], "frame": "Section Y=0; lower face datum X=0,Z=0", "construction": "Lower vertex (0,0), upper vertex (H*tan(rake),H). Camera long axis parallel to panel, actual lens center and cutout to be constrained from mounting drawing.", "acceptance": "Upper edge shift <=110 mm in this assumed example. Verify entire CAD/sensor/connector envelope separately."}],
              "protected_interfaces": [{"id": "I1", "description": "Example clamp datum plane and length/width retained; no actual robot interface is represented.", "evidence_ids": [eid]}],
              "requirements": [{**r, "evidence_ids": [eid]} for r in example_brief()["requirements"]],
              "calculations": calculations,
              "checks": [{"requirement_id": rid, "calculation_ref": ref, "evidence_id": "", "metric": metric, "conditions": "Assumed scenario; analytical screening at the stated inputs, not physical or native CAD verification."} for rid, metric, ref in [("R1", "deflection", "C1.deflection_mm"), ("R2", "stress", "C1.stress_mpa"), ("R3", "factor", "C1.safety_factor"), ("R4", "near_ground", "C2.near_mm"), ("R5", "overhang", "C3.overhang_mm"), ("R6", "minimum_gap", "C4.minimum_gap_mm")]],
              "alternatives": [{"id": "A1", "description": "3 mm bracket, original assumed baseline", "tradeoffs": "12.15 g beam; 32 MPa stress; 0.3710 mm deflection under 20 N", "why_selected_or_rejected": "Reject: exceeds assumed 0.3 mm optical-alignment displacement budget."},
                               {"id": "A2", "description": "4 mm bracket, proposed concept", "tradeoffs": "16.20 g beam; 18 MPa stress; 0.1565 mm deflection; +4.05 g vs baseline", "why_selected_or_rejected": "Propose: passes screening and keeps visual edge bulk below the 5 mm alternative; pending human review."},
                               {"id": "A3", "description": "5 mm bracket, higher stiffness alternative", "tradeoffs": "20.25 g beam; 11.52 MPa stress; 0.0801 mm deflection", "why_selected_or_rejected": "Defer: no stated need for the extra stiffness; +4.05 g and thicker visible edge vs A2."}],
              "aesthetics": {"intent": "Precise, integrated and serviceable; one dominant rake rather than a separate camera bump.", "silhouette": "Single 35-degree front plane; report forward envelope increase even when camera is flush.", "proportions": "150 mm panel height and 105.031 mm forward shift in side section; these are concept dimensions.", "edge_hierarchy": "Proposed main radius 6 mm and secondary radius 2 mm, both assumed and awaiting native/process validation.", "split_lines": "Proposed 1.2 mm seam, worst-case 0.8-1.6 mm under assumed bilateral tolerances.", "cmf": "Neutral matte shell and dark sensor region for shape review; no approved CI or optical-window material is assumed.", "visual_artifact_ids": [visual], "assessment": "Schematic exposes dimensions and tradeoffs. Native orthographic, section and material views remain required for a real product.",
                             "criteria": [{"metric": "Forward silhouette", "target": "Continuous plane without a separate prow, while total overhang <=110 mm", "evaluation": "Side-section diagram and C3; perceived bulk and flush sensor packaging remain human/CAD review items.", "evidence_ids": [view_ev["id"]]},
                                          {"metric": "Service seam", "target": "No contact at worst-case gap >=0.4 mm", "evaluation": "C4 yields minimum 0.8 mm for assumed inputs; a real supplier capability is not established.", "evidence_ids": [assumed["id"]]}]},
              "manufacturing": {"process": "Proposed milled bracket plus separate printed concept shell; process capability unverified.", "material": "Illustrative aluminium-like E=69000 MPa, yield=240 MPa, density=2700 kg/m3; exact grade/temper/source absent.", "datum_scheme": "A mounting face, B primary locating edge, C clocking feature; real hole/fit definitions are unresolved.", "critical_tolerances": "Example shell A/B +/-0.15 mm and alignment +/-0.10 mm; targets only, verify with supplier/coupon.", "assembly_sequence": ["Locate bracket on datum A/B before clamp tightening.", "Install sensor with access to its actual supplier mounting features.", "Fit shell without loading sensor; inspect seam/flushness and cable service path."], "service_access": "Propose rear screw/tool access and a removable front panel; connector path needs an actual CAD envelope.", "supplier_checks": ["Confirm alloy/temper and finish/coating at datum surfaces.", "Confirm cutter access, real holes, edge radii and fixturing.", "Validate printed clearances using same-material/orientation coupons."]},
              "risks": [{"id": "K1", "severity": "major", "status": "open", "description": "Ideal beam excludes holes, vibration, fatigue, fasteners and clamp flexibility.", "next_action": "Use native assembly measurements, joint/load evidence and appropriate structural verification before detail design."},
                        {"id": "K2", "severity": "major", "status": "open", "description": "Pinhole slice does not prove depth-valid scene coverage, optical-window compatibility or motion clearance.", "next_action": "Capture actual camera/configuration, ray/pose domain and measured sensor results."}],
              "change_summary": ["Baseline 3 mm thickness retained in revision 1 to demonstrate a real failed gate."]}
    engine = Engine(store)
    first = engine.submit(project, packet)
    revised = deepcopy(packet)
    next(x for x in revised["parameters"] if x["id"] == "thickness")["value"] = 4
    revised["change_summary"] = ["Increase bracket thickness 3 -> 4 mm; hold length, width, load and panel geometry fixed.",
                                 "Deflection drops 0.3710 -> 0.1565 mm; beam mass rises 12.15 -> 16.20 g; still only a conditional concept study."]
    second = engine.submit(project, revised, first["revision"])
    write_new(output / "proposal-r1.json", (encoded(packet) + '\n').encode())
    write_new(output / "proposal-r2.json", (encoded(revised) + '\n').encode())
    write_new(output / "brief.json", (encoded(example_brief()) + '\n').encode())
    write_new(output / "iteration-diff.json", (encoded(engine.diff(project, first["revision"], second["revision"])) + '\n').encode())
    report = export_review(store, project, second["revision"], output / "review")
    return {"project": project, "baseline_revision": first["revision"], "baseline_ready": first["evaluation"]["engineering_ready"],
            "proposed_revision": second["revision"], "proposed_ready": second["evaluation"]["engineering_ready"],
            "checks": second["evaluation"]["checks"], "review": report, "status": "awaiting_human_review", "human_approval_recorded": False}
