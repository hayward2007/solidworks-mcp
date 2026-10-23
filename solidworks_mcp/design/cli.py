"""Terminal entry point for local investigation, retrieval, review and agent launch."""
import argparse
import asyncio
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from .common import encoded, read_json
from .store import Store
from .tools import dispatch


async def mcp_smoke(home):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=["-m", "solidworks_mcp.design.mcp", "--home", str(home)])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            catalog = await session.list_tools()
            result = await session.call_tool("design_calculate", {"kind": "raked_panel", "inputs": {"height_mm": 150, "rake_deg": 35, "camera_length_mm": 124, "camera_depth_mm": 26}})
            if result.isError:
                raise ValueError("MCP tool call failed")
            decoded = json.loads(result.content[0].text)
            return {"initialized": True, "tools": len(catalog.tools), "tool_call": decoded}


def doctor(home, smoke=False):
    from .retrieval import Retriever
    with Store(home) as store:
        retrieval = Retriever(store)
        retrieval.ensure()
        out = {"python": sys.version.split()[0], "platform": sys.platform, "home": str(store.home),
               "sqlite": sqlite3.sqlite_version, "fts5": True,
               "knowledge_chunks": store.db.execute("SELECT count(*) FROM chunks").fetchone()[0],
               "native_cad_host": os.name == "nt", "win32com_available": bool(importlib.util.find_spec("win32com")),
               "quality_default": True, "model_api_calls": False,
               "native_cad_verified": False}
        if smoke:
            out["mcp"] = asyncio.run(mcp_smoke(store.home))
        return out


def parser():
    root = argparse.ArgumentParser(prog="sw-design", description="Quality-first mechanical reverse engineering and design review. All evidence stays local.")
    root.add_argument("--home", help="Database/artifact directory (default SW_DESIGN_HOME or ~/.solidworks-design)")
    root.add_argument("--pretty", action="store_true", help="Indented JSON output")
    commands = root.add_subparsers(dest="command", required=True)
    p = commands.add_parser("doctor", help="Check local runtime; optionally initialize a real MCP subprocess")
    p.add_argument("--mcp", action="store_true")
    p = commands.add_parser("init", help="Create a project from a quantitative brief JSON")
    p.add_argument("project"); p.add_argument("--brief", required=True)
    p = commands.add_parser("status"); p.add_argument("project")
    p = commands.add_parser("import", help="Preserve artifact bytes and SHA-256")
    p.add_argument("project"); p.add_argument("path")
    p = commands.add_parser("evidence", help="Import a claim JSON: kind, statement, artifact_ids, locator, data")
    p.add_argument("project"); p.add_argument("file")
    p = commands.add_parser("inspect-stl", help="Unit-explicit read-only mesh inspection")
    p.add_argument("project"); p.add_argument("path"); p.add_argument("--unit", choices=["mm", "m", "inch"], required=True)
    p = commands.add_parser("capture", help="Read the active native SolidWorks document on Windows")
    p.add_argument("project")
    p = commands.add_parser("kb", help="Database/RAG: index, search, context, get")
    sub = p.add_subparsers(dest="kb_command", required=True)
    q = sub.add_parser("index"); q.add_argument("--root")
    q = sub.add_parser("search"); q.add_argument("query"); q.add_argument("--limit", type=int, default=8); q.add_argument("--authority")
    q = sub.add_parser("context"); q.add_argument("query"); q.add_argument("--mode", choices=["quality", "compact"], default="quality"); q.add_argument("--limit", type=int, default=10)
    q = sub.add_parser("get"); q.add_argument("id")
    commands.add_parser("schema", help="Strict proposal JSON Schema")
    p = commands.add_parser("calculate"); p.add_argument("kind"); p.add_argument("--inputs", required=True, help="JSON file with explicit inputs in documented units")
    p = commands.add_parser("submit"); p.add_argument("project"); p.add_argument("packet"); p.add_argument("--parent")
    p = commands.add_parser("export"); p.add_argument("project"); p.add_argument("revision"); p.add_argument("--output")
    p = commands.add_parser("diff"); p.add_argument("project"); p.add_argument("before"); p.add_argument("after")
    p = commands.add_parser("review", help="HUMAN ONLY: record review of exact revision after inspecting the export")
    p.add_argument("project"); p.add_argument("revision"); p.add_argument("--decision", choices=["approve", "request_changes", "reject"], required=True)
    p.add_argument("--reviewer", required=True); p.add_argument("--note", required=True)
    p = commands.add_parser("handoff"); p.add_argument("project"); p.add_argument("revision")
    p = commands.add_parser("learn", help="Index an explicitly reviewed revision as a scoped case, preserving assumptions and excluding stale reviews")
    p.add_argument("project"); p.add_argument("revision")
    p = commands.add_parser("demo", help="Run assumed example: failed 3 mm bracket -> passing 4 mm concept; no human approval")
    p.add_argument("--project", default="sensor-front-demo"); p.add_argument("--output", required=True)
    p = commands.add_parser("connect", help="Print client config/argv; --apply registers via installed CLI without replacing an existing entry")
    p.add_argument("--client", choices=["codex", "claude-code", "claude-desktop"], required=True)
    p.add_argument("--apply", action="store_true"); p.add_argument("--cad", action="store_true")
    p = commands.add_parser("start", help="Launch installed agent interactively with project/review instructions")
    p.add_argument("project"); p.add_argument("--agent", choices=["codex", "claude-code"], required=True)
    p = commands.add_parser("serve", help="Start portable MCP on stdio; --cad starts original native server on Windows")
    p.add_argument("--cad", action="store_true")
    return root


def execute(args):
    cmd = args.command
    if cmd == "doctor": return doctor(args.home, args.mcp)
    if cmd == "serve":
        if args.home:
            os.environ["SW_DESIGN_HOME"] = str(Path(args.home).expanduser().resolve())
        if args.cad:
            if os.name != "nt": raise ValueError("native CAD requires Windows and SolidWorks")
            from ..server import run
            run()
        else:
            from .mcp import serve
            asyncio.run(serve(args.home))
        return None
    if cmd == "connect":
        from .clients import connection, apply_connection
        config = connection(args.client, args.home, args.cad)
        return apply_connection(config) if args.apply else config
    if cmd == "start":
        from .clients import start_agent
        raise SystemExit(start_agent(args.agent, args.project, args.home))
    if cmd == "review":
        from .engine import Engine
        with Store(args.home) as store:
            return Engine(store).record_review(args.project, args.revision, args.decision, args.reviewer, args.note)
    if cmd == "demo":
        from .example import make_example
        with Store(args.home) as store:
            return make_example(store, args.project, args.output)
    if cmd == "capture":
        if os.name != "nt": raise ValueError("native capture requires Windows; use the SolidWorks host")
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            app = win32com.client.GetActiveObject("SldWorks.Application")
            return dispatch("design_capture", {"project": args.project}, args.home, native_doc=app.ActiveDoc)
        finally:
            pythoncom.CoUninitialize()
    if cmd == "init": return dispatch("design_project", {"project": args.project, "brief": read_json(args.brief)}, args.home)
    if cmd == "status": return dispatch("design_status", {"project": args.project}, args.home)
    if cmd == "import": return dispatch("design_import", {"project": args.project, "path": args.path}, args.home)
    if cmd == "evidence": return dispatch("design_evidence", {**read_json(args.file), "project": args.project}, args.home)
    if cmd == "inspect-stl": return dispatch("design_inspect_stl", {"project": args.project, "path": args.path, "unit": args.unit}, args.home)
    if cmd == "schema": return dispatch("design_schema", {}, args.home)
    if cmd == "calculate": return dispatch("design_calculate", {"kind": args.kind, "inputs": read_json(args.inputs)}, args.home)
    if cmd == "submit": return dispatch("design_submit", {"project": args.project, "packet": read_json(args.packet), "parent": args.parent}, args.home)
    if cmd == "export": return dispatch("design_review_packet", {"project": args.project, "revision": args.revision, "output": args.output}, args.home)
    if cmd == "diff": return dispatch("design_diff", {"project": args.project, "before": args.before, "after": args.after}, args.home)
    if cmd == "handoff": return dispatch("design_handoff", {"project": args.project, "revision": args.revision}, args.home)
    if cmd == "learn": return dispatch("design_learn", {"project": args.project, "revision": args.revision}, args.home)
    if cmd == "kb":
        if args.kb_command == "index": return dispatch("design_index", {"root": args.root}, args.home)
        if args.kb_command == "get": return dispatch("design_source", {"id": args.id}, args.home)
        if args.kb_command == "search": return dispatch("design_search", {"query": args.query, "limit": args.limit, "authority": args.authority}, args.home)
        return dispatch("design_context", {"query": args.query, "mode": args.mode, "limit": args.limit}, args.home)
    raise ValueError("unknown command")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        out = execute(args)
        if out is not None:
            print(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False) if args.pretty else encoded(out))
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(encoded({"success": False, "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
