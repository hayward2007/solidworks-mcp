"""Strict interchange contract for agent-authored review proposals."""
from copy import deepcopy


def obj(properties, required=None):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else required,
            "additionalProperties": False}


TEXT = {"type": "string", "minLength": 3}
ID = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]{0,79}$"}
NUM = {"type": "number"}
STRINGS = {"type": "array", "items": TEXT, "minItems": 1, "uniqueItems": True}
IDS = {"type": "array", "items": ID, "minItems": 1, "uniqueItems": True}
UNIT = {"enum": ["mm", "mm2", "mm3", "m", "kg", "g", "N", "Nm", "MPa", "kg/m3", "deg", "s", "C", "%", "1"]}


def items(schema, minimum=1):
    return {"type": "array", "items": schema, "minItems": minimum}


PACKET_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **obj({
        "schema_version": {"const": 1}, "title": TEXT, "summary": TEXT,
        "stage": {"enum": ["concept", "detail"]}, "usage": {"enum": ["example", "prototype", "production"]},
        "baseline_artifact_ids": IDS,
        "datums": obj({"origin": TEXT, "axes": {"const": "X forward, Y left, Z up"}, "length_unit": {"const": "mm"}}),
        "parameters": items(obj({"id": ID, "value": NUM, "unit": UNIT,
            "basis": {"enum": ["req", "std", "calc", "cat", "dfm", "heur", "neutral", "assume", "measured"]},
            "evidence_ids": {"type": "array", "items": ID, "uniqueItems": True}, "rationale": TEXT})),
        "geometry": items(obj({"id": ID, "type": TEXT, "parameter_ids": IDS, "frame": TEXT,
                               "construction": TEXT, "acceptance": TEXT})),
        "protected_interfaces": items(obj({"id": ID, "description": TEXT, "evidence_ids": IDS})),
        "requirements": items(obj({"id": ID, "metric": ID, "unit": UNIT, "operator": {"enum": ["le", "ge", "eq"]},
            "limit": NUM, "tolerance": {"type": "number", "minimum": 0}, "critical": {"type": "boolean"},
            "rationale": TEXT, "evidence_ids": IDS})),
        "calculations": items(obj({"id": ID, "kind": {"enum": ["cantilever", "tolerance_stack", "camera_ground", "raked_panel"]},
            "inputs": {"type": "object", "minProperties": 1, "additionalProperties": ID}, "purpose": TEXT}), 0),
        "checks": items(obj({"requirement_id": ID, "calculation_ref": {"type": "string"},
            "evidence_id": {"type": "string"}, "metric": ID, "conditions": TEXT})),
        "alternatives": items(obj({"id": ID, "description": TEXT, "tradeoffs": TEXT, "why_selected_or_rejected": TEXT}), 3),
        "aesthetics": obj({"intent": TEXT, "silhouette": TEXT, "proportions": TEXT, "edge_hierarchy": TEXT,
            "split_lines": TEXT, "cmf": TEXT, "visual_artifact_ids": IDS, "assessment": TEXT,
            "criteria": items(obj({"metric": TEXT, "target": TEXT, "evaluation": TEXT, "evidence_ids": IDS}))}),
        "manufacturing": obj({"process": TEXT, "material": TEXT, "datum_scheme": TEXT, "critical_tolerances": TEXT,
            "assembly_sequence": STRINGS, "service_access": TEXT, "supplier_checks": STRINGS}),
        "risks": items(obj({"id": ID, "severity": {"enum": ["critical", "major", "minor"]},
            "status": {"enum": ["open", "mitigated", "closed"]}, "description": TEXT, "next_action": TEXT}), 0),
        "change_summary": STRINGS,
    })
}


def validate_packet(packet):
    from jsonschema import Draft202012Validator
    errors = sorted(Draft202012Validator(PACKET_SCHEMA).iter_errors(packet), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError("invalid proposal: " + "; ".join(f"{'/'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors[:12]))
    # JSON Schema accepts NaN in Python; canonical encoding must reject it too.
    from .common import encoded
    encoded(packet)
    return deepcopy(packet)
