"""Small reproducible screening models. Units are explicit; these are not FEA."""
import math
from .common import finite


MODELS = {
    "cantilever": {
        "inputs": {"force_n": "N", "length_mm": "mm", "width_mm": "mm", "thickness_mm": "mm",
                   "elastic_modulus_mpa": "MPa", "yield_mpa": "MPa", "density_kg_m3": "kg/m3"},
        "outputs": {"stress_mpa": "MPa", "deflection_mm": "mm", "safety_factor": "1", "mass_kg": "kg"},
        "equations": ["I = width_mm * thickness_mm^3 / 12", "stress_mpa = 6 * force_n * length_mm / (width_mm * thickness_mm^2)", "deflection_mm = force_n * length_mm^3 / (3 * elastic_modulus_mpa * I)", "safety_factor = yield_mpa / stress_mpa", "mass_kg = length_mm * width_mm * thickness_mm * density_kg_m3 * 1e-9"],
        "assumptions": "Prismatic rectangular beam; end transverse point load; ideal clamp; linear elastic small deflection; no holes, stress concentration, fatigue or joint compliance.",
    },
    "tolerance_stack": {
        "inputs": {"gap_mm": "mm", "part_a_tol_mm": "mm", "part_b_tol_mm": "mm", "alignment_tol_mm": "mm"},
        "outputs": {"minimum_gap_mm": "mm", "maximum_gap_mm": "mm", "rss_tol_mm": "mm"},
        "equations": ["T = part_a_tol_mm + part_b_tol_mm + alignment_tol_mm", "minimum_gap_mm = gap_mm - T", "maximum_gap_mm = gap_mm + T", "rss_tol_mm = sqrt(part_a_tol_mm^2 + part_b_tol_mm^2 + alignment_tol_mm^2)"],
        "assumptions": "Symmetric bilateral limits; worst-case arithmetic sum. RSS is informative only; independence and distributions are not established.",
    },
    "camera_ground": {
        "inputs": {"height_mm": "mm", "down_pitch_deg": "deg", "vertical_fov_deg": "deg", "min_range_mm": "mm"},
        "outputs": {"near_mm": "mm", "far_mm": "mm", "near_slant_mm": "mm", "near_range_bound_met": "1"},
        "equations": ["low = down_pitch_deg + vertical_fov_deg / 2", "high = down_pitch_deg - vertical_fov_deg / 2", "near_mm = height_mm / tan(low)", "far_mm = height_mm / tan(high) when high > 0; otherwise unbounded in optical slice", "near_slant_mm = sqrt(height_mm^2 + near_mm^2)", "near_range_bound_met = (near_slant_mm >= min_range_mm); this does not prove valid depth"],
        "assumptions": "Ideal pinhole central vertical slice over flat ground; FOV defined about optical axis; excludes body occlusion, depth quality, resolution and distortion. Range is a caller-specified conservative slant bound.",
    },
    "raked_panel": {
        "inputs": {"height_mm": "mm", "rake_deg": "deg", "camera_length_mm": "mm", "camera_depth_mm": "mm"},
        "outputs": {"overhang_mm": "mm", "camera_x_extent_mm": "mm", "camera_z_extent_mm": "mm"},
        "equations": ["overhang_mm = height_mm * tan(rake_deg)", "camera_x_extent_mm = camera_length_mm * sin(rake_deg) + camera_depth_mm * cos(rake_deg)", "camera_z_extent_mm = camera_length_mm * cos(rake_deg) + camera_depth_mm * sin(rake_deg)"],
        "assumptions": "Side section: X forward, Z up; panel rake from vertical; camera long axis lies along panel. Extents are full box extents, not protrusion from an unspecified pivot.",
    },
}


def calculate(kind, inputs):
    if kind not in MODELS:
        raise ValueError(f"unknown calculation {kind}; choose {', '.join(MODELS)}")
    spec = MODELS[kind]
    if not isinstance(inputs, dict):
        raise ValueError("calculation inputs must be an object")
    if set(inputs) != set(spec["inputs"]):
        raise ValueError(f"{kind} needs exactly {list(spec['inputs'])}")
    p = {k: finite(v, k) for k, v in inputs.items()}
    if kind == "cantilever":
        for k, v in p.items():
            if v <= 0:
                raise ValueError(f"{k} must be positive")
        f, l, b, t = (p[k] for k in ("force_n", "length_mm", "width_mm", "thickness_mm"))
        inertia = b * t ** 3 / 12
        stress = 6 * f * l / (b * t ** 2)
        out = {"stress_mpa": stress, "deflection_mm": f * l ** 3 / (3 * p["elastic_modulus_mpa"] * inertia),
               "safety_factor": p["yield_mpa"] / stress,
               "mass_kg": l * b * t * 1e-9 * p["density_kg_m3"]}
    elif kind == "tolerance_stack":
        tol = [p[k] for k in p if k != "gap_mm"]
        if min(tol) < 0:
            raise ValueError("tolerances cannot be negative")
        out = {"minimum_gap_mm": p["gap_mm"] - sum(tol), "maximum_gap_mm": p["gap_mm"] + sum(tol),
               "rss_tol_mm": math.sqrt(sum(t * t for t in tol))}
    elif kind == "camera_ground":
        h, pitch, fov = p["height_mm"], p["down_pitch_deg"], p["vertical_fov_deg"]
        if h <= 0 or p["min_range_mm"] < 0 or not 0 < fov < 180 or not 0 <= pitch < 90:
            raise ValueError("height>0, min_range>=0, 0<fov<180 and 0<=pitch<90 required")
        low, high = pitch + fov / 2, pitch - fov / 2
        if low >= 90:
            raise ValueError("near ray reaches/passes nadir; this forward-only slice model is inapplicable")
        near = h / math.tan(math.radians(low))
        slant = math.hypot(h, near)
        out = {"near_mm": near, "far_mm": h / math.tan(math.radians(high)) if high > 0 else None,
               "near_slant_mm": slant, "near_range_bound_met": int(slant >= p["min_range_mm"])}
    else:
        if not 0 <= p["rake_deg"] < 90 or min(p[k] for k in p if k != "rake_deg") <= 0:
            raise ValueError("dimensions>0 and 0<=rake_deg<90 required")
        angle = math.radians(p["rake_deg"])
        length, depth = p["camera_length_mm"], p["camera_depth_mm"]
        out = {"overhang_mm": p["height_mm"] * math.tan(angle),
               "camera_x_extent_mm": length * math.sin(angle) + depth * math.cos(angle),
               "camera_z_extent_mm": length * math.cos(angle) + depth * math.sin(angle)}
    for key, value in out.items():
        if value is not None:
            finite(value, key)
    return {"kind": kind, "inputs": p, "input_units": spec["inputs"], "outputs": out,
            "output_units": spec["outputs"], "equations": spec["equations"], "assumptions": spec["assumptions"]}
