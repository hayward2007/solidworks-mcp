"""Local SQLite ledger; all imported artifacts preserve original bytes."""
import json
import mimetypes
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .common import default_home, digest, encoded, now, object_hash, read_json, write_new


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS projects(
 id TEXT PRIMARY KEY, title TEXT NOT NULL, brief TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(
 id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, original_path TEXT NOT NULL,
 stored_path TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS project_artifacts(
 project TEXT REFERENCES projects(id), artifact TEXT REFERENCES artifacts(id),
 PRIMARY KEY(project, artifact));
CREATE TABLE IF NOT EXISTS evidence(
 id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL,
 statement TEXT NOT NULL, artifact_ids TEXT NOT NULL, locator TEXT NOT NULL,
 data TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(
 id TEXT PRIMARY KEY, project TEXT NOT NULL REFERENCES projects(id), ordinal INTEGER NOT NULL,
 parent TEXT REFERENCES revisions(id), packet TEXT NOT NULL, sha256 TEXT NOT NULL,
 created TEXT NOT NULL, UNIQUE(project, ordinal));
CREATE TABLE IF NOT EXISTS reviews(
 id INTEGER PRIMARY KEY, revision TEXT NOT NULL REFERENCES revisions(id),
 decision TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL,
 packet_hash TEXT NOT NULL, evidence_hash TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(
 id TEXT PRIMARY KEY, root TEXT NOT NULL, path TEXT NOT NULL, heading TEXT NOT NULL,
 start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, text TEXT NOT NULL,
 sha256 TEXT NOT NULL, source TEXT NOT NULL, authority TEXT NOT NULL, indexed TEXT NOT NULL);
"""


class Store:
    def __init__(self, home=None):
        self.home = Path(home).expanduser().resolve() if home else default_home()
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.home / "design.sqlite3", timeout=30)
        self._transaction_depth = 0
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        row = self.db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row and row[0] != "1":
            self.close()
            raise ValueError("unsupported database schema; preserve it and use a compatible release")
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('schema_version','1')")

    @contextmanager
    def transaction(self):
        outer = self._transaction_depth == 0
        self._transaction_depth += 1
        try:
            if outer:
                self.db.execute("BEGIN IMMEDIATE")
            yield
            if outer:
                self.db.commit()
        except Exception:
            if outer:
                self.db.rollback()
            raise
        finally:
            self._transaction_depth -= 1

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def project(self, project):
        row = self.db.execute("SELECT * FROM projects WHERE id=?", (project,)).fetchone()
        if not row:
            raise ValueError(f"unknown project: {project}")
        return {**dict(row), "brief": json.loads(row["brief"])}

    def create_project(self, project, brief):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", project):
            raise ValueError("project id must be lowercase letters, numbers and hyphens")
        if not isinstance(brief, dict) or not all(brief.get(k) for k in ("title", "purpose", "requirements")):
            raise ValueError("brief requires title, purpose and nonempty requirements")
        if not all(isinstance(brief[k], str) and len(brief[k].strip()) >= 3 for k in ("title", "purpose")) or not isinstance(brief["requirements"], list):
            raise ValueError("brief title/purpose must be strings and requirements must be an array")
        from jsonschema import Draft202012Validator
        from .schema import PACKET_SCHEMA
        req_schema = PACKET_SCHEMA["properties"]["requirements"]
        # Requirements are assigned the immutable brief evidence after import.
        if not all(isinstance(r, dict) for r in brief["requirements"]):
            raise ValueError("each brief requirement must be an object")
        requirements = [{**r, "evidence_ids": ["brief"]} for r in brief["requirements"]]
        errors = list(Draft202012Validator(req_schema).iter_errors(requirements))
        if errors:
            raise ValueError("invalid brief requirements: " + errors[0].message)
        encoded(brief)
        if len({r["id"] for r in requirements}) != len(requirements):
            raise ValueError("brief requirement ids must be unique")
        from .common import finite
        from .schema import UNIT
        protected = brief.get("protected_parameters", {})
        if not isinstance(protected, dict):
            raise ValueError("protected_parameters must map parameter ids to {value,unit}")
        for pid, value in protected.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,79}", pid) or not isinstance(value, dict) or set(value) != {"value", "unit"}:
                raise ValueError("invalid protected parameter")
            finite(value["value"], pid)
            if value["unit"] not in UNIT["enum"]:
                raise ValueError(f"invalid protected parameter unit: {pid}")
        with self.transaction():
            try:
                self.db.execute("INSERT INTO projects VALUES(?,?,?,?)", (project, brief["title"], encoded(brief), now()))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"project already exists: {project}") from exc
            path = self.home / "briefs" / f"{project}.json"
            data = (encoded(brief) + "\n").encode()
            if path.exists():
                if path.read_bytes() != data:
                    raise ValueError("preserved brief file conflicts with new project; choose another project id")
            else:
                write_new(path, data)
            artifact = self.import_artifact(project, path)
            evidence = self.add_evidence(project, "requirement", brief["purpose"], [artifact["id"]],
                                         "project brief; requirement ids are authoritative", {"requirements": requirements})
        return {"project": project, "brief_artifact_id": artifact["id"], "brief_evidence_id": evidence["id"]}

    def import_artifact(self, project, path):
        self.project(project)
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"not a file: {path}")
        data = path.read_bytes()
        sha = digest(data)
        aid = "a_" + sha[:24]
        stored = self.home / "artifacts" / sha[:2] / sha
        if stored.exists():
            if digest(stored.read_bytes()) != sha:
                raise ValueError(f"corrupted artifact store: {aid}")
        else:
            try:
                write_new(stored, data)
            except FileExistsError:
                if digest(stored.read_bytes()) != sha:
                    raise ValueError(f"corrupted artifact store: {aid}")
        media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?,?)",
                            (aid, sha, str(path), str(stored), media, len(data), now()))
            self.db.execute("INSERT OR IGNORE INTO project_artifacts VALUES(?,?)", (project, aid))
        return self.artifact(project, aid)

    def artifact(self, project, aid):
        row = self.db.execute("SELECT a.* FROM artifacts a JOIN project_artifacts p ON a.id=p.artifact WHERE p.project=? AND a.id=?",
                              (project, aid)).fetchone()
        if not row:
            raise ValueError(f"artifact {aid} is not in project {project}")
        out = dict(row)
        path = Path(out["stored_path"])
        if not path.is_file() or digest(path.read_bytes()) != out["sha256"]:
            raise ValueError(f"missing or changed artifact bytes: {aid}")
        return out

    def add_evidence(self, project, kind, statement, artifact_ids, locator, data=None):
        self.project(project)
        if not isinstance(statement, str) or not isinstance(locator, str) or not isinstance(artifact_ids, list) or not all(isinstance(a, str) for a in artifact_ids) or (data is not None and not isinstance(data, dict)):
            raise ValueError("evidence needs string statement/locator, an artifact id array and a data object")
        if kind not in {"measured", "observed", "reported", "assumed", "requirement", "catalogue", "standard", "test", "simulation"}:
            raise ValueError("unsupported evidence kind")
        if not statement.strip() or not locator.strip() or not artifact_ids:
            raise ValueError("evidence needs statement, artifact_ids and a precise locator/method")
        for aid in artifact_ids:
            self.artifact(project, aid)
        payload = {"project": project, "kind": kind, "statement": statement, "artifact_ids": sorted(set(artifact_ids)),
                   "locator": locator, "data": data or {}}
        eid = "e_" + object_hash(payload)[:24]
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)",
                            (eid, project, kind, statement, encoded(payload["artifact_ids"]), locator, encoded(payload["data"]), now()))
        return self.evidence(project, eid)

    def evidence(self, project, eid):
        row = self.db.execute("SELECT * FROM evidence WHERE project=? AND id=?", (project, eid)).fetchone()
        if not row:
            raise ValueError(f"evidence {eid} is not in project {project}")
        out = dict(row)
        for key in ("artifact_ids", "data"):
            out[key] = json.loads(out[key])
        for aid in out["artifact_ids"]:
            self.artifact(project, aid)
        return out

    def revision(self, project, revision=None):
        self.project(project)
        if revision:
            row = self.db.execute("SELECT * FROM revisions WHERE project=? AND id=?", (project, revision)).fetchone()
        else:
            row = self.db.execute("SELECT * FROM revisions WHERE project=? ORDER BY ordinal DESC LIMIT 1", (project,)).fetchone()
        if not row:
            raise ValueError("revision not found")
        out = dict(row)
        out["packet"] = json.loads(out["packet"])
        if object_hash(out["packet"]) != out["sha256"]:
            raise ValueError("revision hash mismatch")
        return out

    def status(self, project):
        p = self.project(project)
        return {"project": project, "title": p["title"],
                "artifacts": [dict(r) for r in self.db.execute("SELECT a.id,a.sha256,a.media_type FROM artifacts a JOIN project_artifacts p ON p.artifact=a.id WHERE p.project=?", (project,))],
                "evidence": [{"id": r["id"], "kind": r["kind"], "statement": r["statement"]} for r in self.db.execute("SELECT * FROM evidence WHERE project=?", (project,))],
                "revisions": [dict(r) for r in self.db.execute("SELECT id,ordinal,parent,sha256,created FROM revisions WHERE project=? ORDER BY ordinal", (project,))]}
