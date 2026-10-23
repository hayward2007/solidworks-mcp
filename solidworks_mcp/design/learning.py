"""Promote an explicitly reviewed revision to a scoped, searchable case, never a standard."""
from .common import encoded, write_new
from .engine import Engine
from .retrieval import Retriever


def learn_case(store, project, revision):
    engine = Engine(store)
    handoff = engine.handoff(project, revision)
    rev = store.revision(project, revision)
    p = rev["packet"]
    gate = engine.evaluate(project, p)
    title = p["title"].replace('\n', ' ').replace('\r', ' ')
    lines = ["---", "title: Reviewed design case - " + title,
             "tags: reviewed case, design iteration, 설계 예제, 검토, 반복, " + title,
             "authority: reviewed_case", f"source: review:{project}/{revision}",
             "checked: " + handoff["review"]["created"],
             f"applicability: {p['stage']} / {p['usage']}; this exact scenario only; not a general design rule or standard",
             f"project: {project}", f"revision: {revision}", f"review_id: {handoff['review']['id']}", "---", "# Reviewed design case", "",
             "## Scope and provenance", p["summary"],
             f"Stage: {p['stage']}; usage: {p['usage']}. Production certified: false.",
             "This case retains its assumptions and limitations. Human review does not convert example inputs into measurements or standards.",
             f"Packet SHA-256: {gate['packet_hash']}", f"Evidence SHA-256: {gate['evidence_hash']}", "",
             "## Parameter and evidence ledger", "```json", encoded(p["parameters"]), "```", "",
             "## Quantitative requirements and outcomes", "```json", encoded(gate["checks"]), "```", "",
             "## Geometry and protected interfaces", "```json", encoded({"datums": p["datums"], "geometry": p["geometry"], "protected_interfaces": p["protected_interfaces"]}), "```", "",
             "## Alternatives and selection rationale", "```json", encoded(p["alternatives"]), "```", "",
             "## Appearance and manufacturing guide for this scenario", "```json", encoded({"aesthetics": p["aesthetics"], "manufacturing": p["manufacturing"]}), "```", "",
             "## Risks and applicability limits", "```json", encoded({"risks": p["risks"], "warnings": gate["warnings"], "models": gate["calculations"]}), "```", ""]
    data = '\n'.join(lines).encode('utf-8')
    root = store.home / "learned"
    path = root / f"{project}-{revision}-review{handoff['review']['id']}.md"
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("learned case already exists with different contents; preserve it and create a new reviewed revision")
    else:
        write_new(path, data)
    indexed = Retriever(store).index(root)
    return {"path": str(path), "authority": "reviewed_case", "stage": p["stage"], "usage": p["usage"],
            "revision": revision, "indexed": indexed, "production_certified": False,
            "note": "This scoped case is excluded from retrieval if its revision/review fingerprint becomes stale or revoked."}
