"""Versioned proposals, numerical gates and human-review handoffs.

These gates govern Design Studio handoffs. They cannot sandbox another agent's
shell or the existing arbitrary execute_python tool.
"""
import json
import math
from pathlib import Path
from .common import encoded, finite, now, object_hash, digest
from .schema import validate_packet
from .calculations import MODELS, calculate


class Engine:
    def __init__(self, store):
        self.store, self.db = store, store.db

    def evaluate(self, project, packet):
        p = validate_packet(packet)
        brief = self.store.project(project)["brief"]
        blockers, warnings, results, evidence, artifacts = [], [], [], {}, {}

        def block(code, detail):
            blockers.append({"code": code, "detail": detail})

        def get_evidence(eid):
            if eid not in evidence:
                evidence[eid] = self.store.evidence(project, eid)
            return evidence[eid]

        def get_artifact(aid):
            if aid not in artifacts:
                artifacts[aid] = self.store.artifact(project, aid)
            return artifacts[aid]

        def unique(rows, label, key="id"):
            out = {}
            for row in rows:
                if row[key] in out:
                    raise ValueError(f"duplicate {label} id: {row[key]}")
                out[row[key]] = row
            return out

        params = unique(p["parameters"], "parameter")
        reqs = unique(p["requirements"], "requirement")
        unique(p["geometry"], "geometry")
        unique(p["alternatives"], "alternative")
        unique(p["protected_interfaces"], "protected interface")
        unique(p["risks"], "risk")
        unique(p["checks"], "requirement check", "requirement_id")
        for aid in p["baseline_artifact_ids"] + p["aesthetics"]["visual_artifact_ids"]:
            get_artifact(aid)
        for aid in p["aesthetics"]["visual_artifact_ids"]:
            if artifacts[aid]["media_type"] not in {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "application/pdf"}:
                block("visual_format", f"{aid} must be an image or PDF for visual review")

        for group in (p["parameters"], p["requirements"], p["protected_interfaces"], p["aesthetics"]["criteria"]):
            for row in group:
                for eid in row["evidence_ids"]:
                    get_evidence(eid)
        basis_kinds = {"std": {"standard"}, "cat": {"catalogue"}, "measured": {"measured"}, "req": {"requirement", "measured"}}
        for row in params.values():
            finite(row["value"], row["id"])
            if row["basis"] not in {"neutral", "assume"} and not row["evidence_ids"]:
                block("parameter_basis", f"{row['id']} requires supporting evidence")
            if row["basis"] in basis_kinds and not any(evidence[e]["kind"] in basis_kinds[row["basis"]] for e in row["evidence_ids"]):
                block("basis_mismatch", f"{row['id']}: {row['basis']} does not match evidence kind")
            if row["basis"] in {"neutral", "assume"}:
                warnings.append(f"{row['id']} is {row['basis']}; value {row['value']} {row['unit']} requires later confirmation")
        for geo in p["geometry"]:
            missing = set(geo["parameter_ids"]) - params.keys()
            if missing:
                raise ValueError(f"geometry {geo['id']} has unknown parameters {sorted(missing)}")

        for authoritative in brief["requirements"]:
            candidate = reqs.get(authoritative["id"])
            if candidate is None:
                block("requirement_removed", authoritative["id"])
            else:
                for key in ("metric", "unit", "operator", "limit", "tolerance", "critical"):
                    if candidate[key] != authoritative[key]:
                        block("requirement_changed", f"{authoritative['id']}.{key}: edit requires a new reviewed project brief")
        for pid, fixed in brief.get("protected_parameters", {}).items():
            candidate = params.get(pid)
            if candidate is None or any(candidate.get(k) != fixed[k] for k in ("value", "unit")):
                block("protected_parameter_changed", f"{pid}: must preserve {fixed['value']} {fixed['unit']} from the brief")

        calculated = {}
        for calc in p["calculations"]:
            if calc["id"] in calculated:
                raise ValueError(f"duplicate calculation {calc['id']}")
            spec = MODELS[calc["kind"]]
            inputs = {}
            for name, pid in calc["inputs"].items():
                if pid not in params:
                    raise ValueError(f"unknown calculation parameter {pid}")
                if params[pid]["unit"] != spec["inputs"].get(name):
                    raise ValueError(f"unit mismatch: {pid} -> {calc['id']}.{name}")
                inputs[name] = params[pid]["value"]
            calculated[calc["id"]] = calculate(calc["kind"], inputs)

        checked = set()
        for check in p["checks"]:
            rid = check["requirement_id"]
            if rid not in reqs:
                raise ValueError(f"unknown checked requirement {rid}")
            req = reqs[rid]
            checked.add(rid)
            if bool(check["calculation_ref"]) == bool(check["evidence_id"]):
                raise ValueError(f"{rid} must reference exactly one calculation or evidence")
            if check["metric"] != req["metric"]:
                raise ValueError(f"{rid}: metric differs from requirement")
            validity, source, uncertainty = True, "", 0.0
            if check["calculation_ref"]:
                try:
                    cid, metric = check["calculation_ref"].split(".", 1)
                    value = calculated[cid]["outputs"][metric]
                    unit = calculated[cid]["output_units"][metric]
                except (ValueError, KeyError) as exc:
                    raise ValueError(f"invalid calculation reference {check['calculation_ref']}") from exc
                source = check["calculation_ref"]
                # A calculation that depends on an assumption is a conditional result.
                unconfirmed = [pid for pid in next(c for c in p["calculations"] if c["id"] == cid)["inputs"].values()
                               if params[pid]["basis"] in {"assume", "neutral"}]
                if unconfirmed and req["critical"] and p["stage"] == "detail":
                    block("critical_assumption", f"{rid}: calculation inputs {unconfirmed} remain unconfirmed")
            else:
                ev = get_evidence(check["evidence_id"])
                entry = ev["data"].get("metrics", {}).get(check["metric"])
                if not isinstance(entry, dict) or "value" not in entry or "unit" not in entry:
                    raise ValueError(f"{rid}: evidence must include metrics.{check['metric']}.value and unit")
                value, unit = entry["value"], entry["unit"]
                if entry.get("uncertainty") is None:
                    validity = False
                    block("measurement_uncertainty_missing", f"{rid}: specify metric uncertainty in the same unit, even if the explicitly justified bound is zero")
                else:
                    uncertainty = finite(entry["uncertainty"], f"{rid} uncertainty")
                    if uncertainty < 0:
                        raise ValueError(f"{rid}: uncertainty cannot be negative")
                kind_valid = ev["kind"] in {"measured", "test", "simulation"}
                validity = validity and kind_valid
                source = ev["id"]
                if not kind_valid:
                    block("unverified_check", f"{rid}: {ev['kind']} evidence cannot satisfy a check")
            if unit != req["unit"]:
                raise ValueError(f"{rid}: output unit {unit} != {req['unit']}")
            if value is None:
                passed, margin = False, None
            else:
                value = finite(value, rid)
                delta = value - req["limit"]
                margin = ((-delta if req["operator"] == "le" else delta) if req["operator"] != "eq" else req["tolerance"] - abs(delta)) - uncertainty
                # Tolerance expands only an equality band, never relaxes a safety limit.
                passed = validity and (margin >= -1e-12)
            results.append({"requirement_id": rid, "metric": req["metric"], "value": value, "unit": unit,
                            "operator": req["operator"], "limit": req["limit"], "tolerance": req["tolerance"],
                            "uncertainty": uncertainty,
                            "margin": margin, "passed": passed, "source": source, "conditions": check["conditions"]})
            if not passed:
                block("requirement_failed", rid)
        for missing in reqs.keys() - checked:
            block("requirement_unchecked", missing)
        for risk in p["risks"]:
            if risk["severity"] == "critical" and risk["status"] != "closed":
                block("critical_risk", risk["description"])
        if p["stage"] == "detail":
            snapshots = [e for e in evidence.values() if e["data"].get("capture_type") == "solidworks-native"]
            if not snapshots:
                block("native_verification_missing", "detail stage needs linked native SolidWorks snapshot evidence")
            for snap in snapshots:
                report = snap["data"].get("report", {})
                if not report or "errors" not in report or report["errors"] or snap["data"].get("incomplete") or not snap["data"].get("configuration"):
                    block("native_verification_failed", snap["id"])
        if p["usage"] == "production":
            if p["stage"] != "detail" or not any(e["kind"] == "test" for e in evidence.values()):
                block("production_validation_missing", "production requires detail-stage native evidence and physical test evidence")
            if any(x["basis"] in {"neutral", "assume"} for x in params.values()):
                block("production_assumption", "production parameters cannot remain assumed/neutral")
        # Include every referenced evidence artifact in the approval fingerprint.
        for ev in evidence.values():
            for aid in ev["artifact_ids"]:
                get_artifact(aid)
        from .retrieval import knowledge_root, MANDATORY
        rule_hashes = {name: digest((Path(__file__).parent / name).read_bytes()) for name in ("engine.py", "calculations.py", "schema.py")}
        policy_hashes = {name: digest((knowledge_root() / (name + ".md")).read_bytes()) for name in MANDATORY}
        fingerprint = object_hash({"artifacts": {a: v["sha256"] for a, v in sorted(artifacts.items())},
                                   "evidence": {e: {k: v for k, v in item.items() if k != "created"} for e, item in sorted(evidence.items())},
                                   "brief": brief, "rule_hashes": rule_hashes, "policy_hashes": policy_hashes,
                                   "calculation_results": calculated, "checks": results})
        return {"engineering_ready": not blockers, "human_review_required": True,
                "production_certified": False, "stage": p["stage"], "usage": p["usage"],
                "blockers": blockers, "warnings": warnings, "checks": results, "calculations": calculated,
                "packet_hash": object_hash(p), "evidence_hash": fingerprint,
                "rule_hashes": rule_hashes, "policy_hashes": policy_hashes,
                "artifacts": list(artifacts.values()), "evidence": list(evidence.values()),
                "limits": ["Analytical screening is not FEA or physical validation.",
                           "Appearance acceptance requires human visual review.",
                           "Evidence kinds/authority are recorded declarations; inspect original artifacts."]}

    def submit(self, project, packet, parent=None):
        packet = validate_packet(packet)
        evaluation = self.evaluate(project, packet)
        # Lock before reading latest revision: parallel clients cannot both claim the same parent.
        try:
            self.db.execute("BEGIN IMMEDIATE")
            latest = self.db.execute("SELECT id,ordinal FROM revisions WHERE project=? ORDER BY ordinal DESC LIMIT 1", (project,)).fetchone()
            if (latest and parent != latest["id"]) or (not latest and parent is not None):
                raise ValueError("parent must be the current latest revision; inspect project status before resubmitting")
            ordinal = latest["ordinal"] + 1 if latest else 1
            rid = "r_" + object_hash([project, ordinal, parent, packet])[:24]
            self.db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?,?)",
                            (rid, project, ordinal, parent, encoded(packet), object_hash(packet), now()))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"revision": rid, "ordinal": ordinal, "status": "awaiting_review" if evaluation["engineering_ready"] else "blocked",
                "evaluation": evaluation}

    def record_review(self, project, revision, decision, reviewer, note):
        if decision not in {"approve", "request_changes", "reject"} or not reviewer.strip() or not note.strip():
            raise ValueError("review requires decision, reviewer and review note")
        rev = self.store.revision(project, revision)
        gate = self.evaluate(project, rev["packet"])
        if decision == "approve" and not gate["engineering_ready"]:
            raise ValueError("cannot approve: resolve engineering blockers first")
        if self.store.revision(project)["id"] != revision:
            raise ValueError("cannot review a superseded revision")
        with self.db:
            cursor = self.db.execute("INSERT INTO reviews(revision,decision,reviewer,note,packet_hash,evidence_hash,created) VALUES(?,?,?,?,?,?,?)",
                                    (revision, decision, reviewer, note, gate["packet_hash"], gate["evidence_hash"], now()))
        return {"review_id": cursor.lastrowid, "revision": revision, "decision": decision, "reviewer": reviewer}

    def handoff(self, project, revision):
        rev = self.store.revision(project, revision)
        if self.store.revision(project)["id"] != revision:
            raise ValueError("revision superseded; submit and review the latest design")
        gate = self.evaluate(project, rev["packet"])
        review = self.db.execute("SELECT * FROM reviews WHERE revision=? ORDER BY id DESC LIMIT 1", (revision,)).fetchone()
        if not gate["engineering_ready"] or not review or review["decision"] != "approve":
            raise ValueError("implementation handoff unavailable: passing gates and an explicit human review are required")
        if review["packet_hash"] != gate["packet_hash"] or review["evidence_hash"] != gate["evidence_hash"]:
            raise ValueError("review fingerprint is stale; review again")
        return {"project": project, "revision": revision, "packet_hash": gate["packet_hash"],
                "review": dict(review), "scope": rev["packet"]["stage"], "usage": rev["packet"]["usage"],
                "production_certified": False, "geometry": rev["packet"]["geometry"],
                "parameters": rev["packet"]["parameters"], "protected_interfaces": rev["packet"]["protected_interfaces"],
                "instructions": ["Create a new CAD copy/configuration and preserve the source baseline.",
                                 "Implement only reviewed parameter groups; capture actual dimensions and matching views after each stage.",
                                 "A material geometry change needs a new proposal, measurements and review."]}

    def diff(self, project, before, after):
        old, new = (self.store.revision(project, x)["packet"] for x in (before, after))
        sections = {}
        for key in new:
            if old.get(key) != new[key]:
                sections[key] = {"before": old.get(key), "after": new[key]}
        return {"before": before, "after": after, "changes": sections}
