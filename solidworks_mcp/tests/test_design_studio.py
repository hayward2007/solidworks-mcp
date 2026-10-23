"""End-to-end evidence/retrieval/review tests. No native CAD execution is claimed."""
import asyncio
import importlib.util
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from solidworks_mcp.design.calculations import calculate
from solidworks_mcp.design.clients import connection, apply_connection, start_agent
from solidworks_mcp.design.common import read_json
from solidworks_mcp.design.engine import Engine
from solidworks_mcp.design.example import make_example, example_brief
from solidworks_mcp.design.inspect import inspect_stl
from solidworks_mcp.design.retrieval import Retriever, MANDATORY
from solidworks_mcp.design.store import Store
from solidworks_mcp.design.tools import definitions, dispatch


class Calculations(unittest.TestCase):
    def test_cantilever_independent_values(self):
        p = {"force_n": 20, "length_mm": 60, "width_mm": 25, "thickness_mm": 4,
             "elastic_modulus_mpa": 69000, "yield_mpa": 240, "density_kg_m3": 2700}
        out = calculate("cantilever", p)["outputs"]
        self.assertAlmostEqual(out["stress_mpa"], 18)
        self.assertAlmostEqual(out["deflection_mm"], 0.1565217391304348)
        self.assertAlmostEqual(out["mass_kg"], 0.0162)
        self.assertAlmostEqual(out["safety_factor"], 13.333333333333)
        with self.assertRaises(ValueError): calculate("cantilever", {**p, "thickness_mm": 0})
        with self.assertRaises(ValueError): calculate("cantilever", {**p, "force_n": float("nan")})
        with self.assertRaises(ValueError): calculate("cantilever", {**p, "force_n": True})

    def test_worst_case_and_invalid_tolerance(self):
        p = {"gap_mm": 1.2, "part_a_tol_mm": .15, "part_b_tol_mm": .15, "alignment_tol_mm": .1}
        out = calculate("tolerance_stack", p)["outputs"]
        self.assertAlmostEqual(out["minimum_gap_mm"], .8)
        self.assertAlmostEqual(out["maximum_gap_mm"], 1.6)
        self.assertAlmostEqual(out["rss_tol_mm"], math.sqrt(.055))
        with self.assertRaises(ValueError): calculate("tolerance_stack", {**p, "alignment_tol_mm": -.1})

    def test_ground_horizon_and_range(self):
        p = {"height_mm": 1000, "down_pitch_deg": 45, "vertical_fov_deg": 30, "min_range_mm": 2000}
        out = calculate("camera_ground", p)["outputs"]
        self.assertAlmostEqual(out["near_mm"], 1000 / math.sqrt(3))
        self.assertAlmostEqual(out["far_mm"], 1000 * math.sqrt(3))
        self.assertEqual(out["near_range_bound_met"], 0)
        self.assertIsNone(calculate("camera_ground", {**p, "down_pitch_deg": 10})["outputs"]["far_mm"])
        with self.assertRaises(ValueError): calculate("camera_ground", {**p, "down_pitch_deg": 80})

    def test_projection_is_full_box_not_tip_motion(self):
        p = {"height_mm": 150, "rake_deg": 0, "camera_length_mm": 124, "camera_depth_mm": 26}
        out = calculate("raked_panel", p)["outputs"]
        self.assertEqual(out, {"overhang_mm": 0, "camera_x_extent_mm": 26, "camera_z_extent_mm": 124})
        self.assertAlmostEqual(calculate("raked_panel", {**p, "rake_deg": 35})["outputs"]["overhang_mm"], 105.03113073145646)


class TemporaryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()


class Retrieval(TemporaryStore):
    def test_bilingual_retrieval_provenance_and_refresh(self):
        root = self.root / "kb"; root.mkdir()
        source = root / "sensor.md"
        source.write_text("---\ntitle: Camera optics\nauthority: catalogue\nsource: https://example.invalid/drawing\nchecked: 2026-10-21\napplicability: example only\n---\n# Camera\n\n## Ground\nCamera optical field view occlusion.\n", encoding="utf-8")
        r = Retriever(self.store)
        self.assertEqual(r.index(root)["files"], 1)
        hits = r.search("카메라 시야")
        self.assertTrue(hits)
        self.assertIn("sensor.md:", hits[0]["citation"])
        self.assertEqual(hits[0]["authority"], "catalogue")
        ref = hits[0]["id"]
        source.write_text("## Replacement\nChanged data", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"): r.get(ref)
        r.index(root)
        with self.assertRaises(ValueError): r.get(ref)
        source.unlink(); r.index(root)
        self.assertFalse(r.search("카메라", 5))

    def test_quality_context_keeps_mandatory_policies(self):
        r = Retriever(self.store)
        result = r.context("카메라 역경사 디자인")
        self.assertEqual(result["mode"], "quality")
        self.assertGreater(len(result["chunks"]), 3)
        paths = {Path(c["path"]).stem for c in result["chunks"]}
        self.assertTrue(set(MANDATORY) <= paths)
        self.assertFalse(any(c.get("truncated") for c in result["chunks"]))
        compact = r.context("카메라 역경사 디자인", "compact")
        for row in compact["chunks"]:
            if Path(row["path"]).stem in MANDATORY:
                self.assertFalse(row.get("truncated"))

    def test_empty_and_query_operators_do_not_execute_sql(self):
        r = Retriever(self.store); r.index()
        self.assertEqual(r.search(""), [])
        r.search('" OR 1=1; DROP TABLE chunks; --')
        self.assertGreater(self.store.db.execute("SELECT count(*) FROM chunks").fetchone()[0], 0)
        with self.assertRaises(ValueError): r.search("camera", 500)


class Initialization(TemporaryStore):
    def test_partial_project_creation_rolls_back_and_preserves_existing_file(self):
        target = self.store.home / "briefs" / "collision.json"
        target.parent.mkdir()
        target.write_text("preserved original")
        with self.assertRaisesRegex(ValueError, "conflicts"): self.store.create_project("collision", example_brief())
        self.assertEqual(target.read_text(), "preserved original")
        with self.assertRaisesRegex(ValueError, "unknown project"): self.store.project("collision")

    def test_bad_brief_and_claim_fail_with_useful_errors(self):
        with self.assertRaises(ValueError): self.store.create_project("bad", {**example_brief(), "requirements": [42]})
        self.store.create_project("good", example_brief())
        with self.assertRaises(ValueError): self.store.add_evidence("good", "measured", "some fact", [], "locator", ["not an object"])


class LedgerAndReview(TemporaryStore):
    def setUp(self):
        super().setUp()
        self.demo = make_example(self.store, "demo", self.root / "example")
        self.engine = Engine(self.store)
        self.r1, self.r2 = self.demo["baseline_revision"], self.demo["proposed_revision"]
        self.packet = self.store.revision("demo", self.r2)["packet"]

    def test_real_iteration_fail_then_pass_without_approval(self):
        self.assertFalse(self.demo["baseline_ready"])
        self.assertTrue(self.demo["proposed_ready"])
        self.assertFalse(self.demo["human_approval_recorded"])
        self.assertEqual(len(self.demo["checks"]), 6)
        with self.assertRaisesRegex(ValueError, "human review"): self.engine.handoff("demo", self.r2)
        self.assertIn("parameters", self.engine.diff("demo", self.r1, self.r2)["changes"])

    def test_learning_requires_review_and_revocation_removes_active_rag_case(self):
        from solidworks_mcp.design.learning import learn_case
        from solidworks_mcp.design.retrieval import CaseUnavailable
        with self.assertRaises(ValueError): learn_case(self.store, "demo", self.r2)
        self.engine.record_review("demo", self.r2, "approve", "Test reviewer", "Explicit test-only concept review")
        case = learn_case(self.store, "demo", self.r2)
        self.assertEqual(case["usage"], "example")
        retriever = Retriever(self.store)
        hits = retriever.search("bracket", 10, "reviewed_case")
        self.assertTrue(hits)
        self.assertIn("not a general design rule", hits[0]["source"]["applicability"])
        ref = hits[0]["id"]
        self.engine.record_review("demo", self.r2, "reject", "Test reviewer", "Revoke test case")
        self.assertEqual(retriever.search("bracket", 10, "reviewed_case"), [])
        with self.assertRaises(CaseUnavailable): retriever.get(ref)

    def test_explicit_review_then_change_request_revokes_handoff(self):
        self.engine.record_review("demo", self.r2, "approve", "Test reviewer", "Test-only concept review")
        handoff = self.engine.handoff("demo", self.r2)
        self.assertEqual(handoff["usage"], "example")
        self.assertFalse(handoff["production_certified"])
        self.engine.record_review("demo", self.r2, "request_changes", "Test reviewer", "Revise the service approach")
        with self.assertRaises(ValueError): self.engine.handoff("demo", self.r2)

    def test_changed_revision_requires_new_review(self):
        self.engine.record_review("demo", self.r2, "approve", "Test reviewer", "Test-only review")
        changed = deepcopy(self.packet); changed["aesthetics"]["intent"] = "A changed visual intent requiring review"
        r3 = self.engine.submit("demo", changed, self.r2)["revision"]
        with self.assertRaises(ValueError): self.engine.handoff("demo", self.r2)
        with self.assertRaises(ValueError): self.engine.handoff("demo", r3)
        with self.assertRaises(ValueError): self.engine.record_review("demo", self.r2, "approve", "Tester", "Old revision")

    def test_changed_calculation_assumptions_invalidate_review(self):
        from solidworks_mcp.design.calculations import MODELS
        self.engine.record_review("demo", self.r2, "approve", "Test reviewer", "Test-only review")
        changed = {**MODELS["cantilever"], "assumptions": "A material change in model applicability"}
        with patch.dict(MODELS, {"cantilever": changed}):
            with self.assertRaisesRegex(ValueError, "stale"): self.engine.handoff("demo", self.r2)

    def test_protected_parameter_value_and_unit_are_enforced(self):
        brief = example_brief()
        brief["protected_parameters"] = {"width": {"value": 25, "unit": "mm"}}
        # Use another scoped project; attach the same bytes, create its own evidence ids.
        row = self.store.db.execute("SELECT brief FROM projects WHERE id='demo'").fetchone()
        original = row[0]
        try:
            self.store.db.execute("UPDATE projects SET brief=? WHERE id='demo'", (json.dumps(brief),))
            self.store.db.commit()
            p = deepcopy(self.packet)
            next(x for x in p["parameters"] if x["id"] == "width")["value"] = 26
            self.assertIn("protected_parameter_changed", {b["code"] for b in self.engine.evaluate("demo", p)["blockers"]})
        finally:
            self.store.db.execute("UPDATE projects SET brief=? WHERE id='demo'", (original,))
            self.store.db.commit()

    def test_measured_bound_uses_uncertainty_conservatively(self):
        aid = self.packet["baseline_artifact_ids"][0]
        ev = self.store.add_evidence("demo", "measured", "Test-only measured displacement with uncertainty", [aid], "Test fixture output; not product evidence",
                                     {"metrics": {"deflection": {"value": .29, "unit": "mm", "uncertainty": .02}}})
        p = deepcopy(self.packet); p["checks"][0].update(calculation_ref="", evidence_id=ev["id"])
        gate = self.engine.evaluate("demo", p)
        self.assertFalse(gate["checks"][0]["passed"])
        self.assertAlmostEqual(gate["checks"][0]["margin"], -.01)

    def test_capture_metric_format_satisfies_a_check(self):
        from solidworks_mcp.design.inspect import _metric
        aid = self.packet["baseline_artifact_ids"][0]
        ev = self.store.add_evidence("demo", "measured", "Test-only metric in the design_capture format", [aid], "Test fixture output; not product evidence",
                                     {"metrics": {"deflection": _metric(.25, "mm", .00052, "test-only basis")}})
        p = deepcopy(self.packet); p["checks"][0].update(calculation_ref="", evidence_id=ev["id"])
        gate = self.engine.evaluate("demo", p)
        self.assertTrue(gate["checks"][0]["passed"])
        self.assertAlmostEqual(gate["checks"][0]["margin"], .3 - .25 - .00052)
        self.assertNotIn("measurement_uncertainty_missing", {b["code"] for b in gate["blockers"]})

    def test_wrong_parent_and_failed_revision_cannot_be_approved(self):
        with self.assertRaisesRegex(ValueError, "parent"): self.engine.submit("demo", self.packet)
        bad = deepcopy(self.packet)
        next(p for p in bad["parameters"] if p["id"] == "thickness")["value"] = 2
        rid = self.engine.submit("demo", bad, self.r2)["revision"]
        with self.assertRaisesRegex(ValueError, "blockers"): self.engine.record_review("demo", rid, "approve", "Test", "Invalid")

    def test_corrupted_stored_artifact_blocks_review(self):
        aid = self.packet["baseline_artifact_ids"][0]
        artifact = self.store.artifact("demo", aid)
        self.engine.record_review("demo", self.r2, "approve", "Test reviewer", "Test-only review")
        Path(artifact["stored_path"]).write_bytes(b"modified")
        with self.assertRaisesRegex(ValueError, "changed artifact"): self.engine.handoff("demo", self.r2)

    def test_import_preserves_original_bytes_after_source_changes(self):
        source = self.root / "original.txt"; source.write_text("before", encoding="utf-8")
        a = self.store.import_artifact("demo", source)
        source.write_text("after", encoding="utf-8")
        self.assertEqual(Path(self.store.artifact("demo", a["id"])["stored_path"]).read_text(), "before")
        self.assertNotEqual(a["id"], self.store.import_artifact("demo", source)["id"])

    def test_project_isolation(self):
        self.store.create_project("other", example_brief())
        with self.assertRaises(ValueError): self.engine.evaluate("other", self.packet)
        with self.assertRaises(ValueError): self.store.revision("other", self.r2)

    def test_requirement_weakening_and_removal_are_blocked(self):
        for mutation in ("weaken", "remove"):
            p = deepcopy(self.packet)
            if mutation == "weaken": p["requirements"][0]["limit"] = 500
            else:
                p["requirements"].pop(0); p["checks"].pop(0)
            gate = self.engine.evaluate("demo", p)
            self.assertFalse(gate["engineering_ready"])
            self.assertTrue(any(b["code"].startswith("requirement_") for b in gate["blockers"]))

    def test_unknown_references_duplicate_ids_and_units_fail(self):
        mutations = [lambda p: p["parameters"].append(deepcopy(p["parameters"][0])),
                     lambda p: p["parameters"][0].update(unit="mm"),
                     lambda p: p["geometry"][0]["parameter_ids"].append("missing"),
                     lambda p: p["checks"][0].update(calculation_ref="C99.missing"),
                     lambda p: p["checks"][0].update(evidence_id="also-not-allowed"),
                     lambda p: p["aesthetics"].update(visual_artifact_ids=[p["baseline_artifact_ids"][0]])]
        for change in mutations:
            p = deepcopy(self.packet); change(p)
            try:
                gate = self.engine.evaluate("demo", p)
                self.assertFalse(gate["engineering_ready"])
            except ValueError:
                pass

    def test_detail_requires_native_and_production_requires_test(self):
        p = deepcopy(self.packet); p.update(stage="detail", usage="production")
        gate = self.engine.evaluate("demo", p)
        codes = {b["code"] for b in gate["blockers"]}
        self.assertTrue({"native_verification_missing", "production_validation_missing", "critical_assumption"} <= codes)

    def test_reported_measurements_do_not_pass(self):
        aid = self.packet["baseline_artifact_ids"][0]
        ev = self.store.add_evidence("demo", "reported", "Someone said displacement is tiny", [aid], "Example claim, not a measurement",
                                     {"metrics": {"deflection": {"value": .01, "unit": "mm"}}})
        p = deepcopy(self.packet); p["checks"][0].update(calculation_ref="", evidence_id=ev["id"])
        gate = self.engine.evaluate("demo", p)
        self.assertFalse(gate["checks"][0]["passed"])
        self.assertIn("unverified_check", {b["code"] for b in gate["blockers"]})

    def test_manifest_and_html_escape(self):
        from solidworks_mcp.design.report import export_review
        from solidworks_mcp.design.common import digest
        review = Path(self.demo["review"]["directory"])
        manifest = read_json(review / "manifest.json")
        for name, sha in manifest["files"].items(): self.assertEqual(digest((review / name).read_bytes()), sha)
        p = deepcopy(self.packet); p["title"] = '<script>alert("unsafe")</script>'
        rev = self.engine.submit("demo", p, self.r2)["revision"]
        out = export_review(self.store, "demo", rev, self.root / "escaped")
        document = Path(out["html"]).read_text(encoding="utf-8")
        self.assertNotIn('<script>alert(', document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("Content-Security-Policy", document)
        with self.assertRaises(ValueError): export_review(self.store, "demo", rev, self.root / "escaped")

    def test_schema_rejects_unbounded_or_invented_fields(self):
        for change in (lambda p: p.update(extra="invented"), lambda p: p["parameters"][0].update(value=float("inf")),
                       lambda p: p.update(alternatives=p["alternatives"][:2]), lambda p: p["aesthetics"].update(silhouette="")):
            p = deepcopy(self.packet); change(p)
            with self.assertRaises(ValueError): self.engine.evaluate("demo", p)


class Meshes(unittest.TestCase):
    def write_tetra(self, path, binary=False, missing=False):
        a,b,c,d = (0,0,0),(1,0,0),(0,1,0),(0,0,1)
        tris = [(a,c,b),(a,b,d),(a,d,c),(b,c,d)]
        if missing: tris.pop()
        if binary:
            path.write_bytes(b"solid binary header".ljust(80,b" ") + struct.pack("<I",len(tris)) + b"".join(struct.pack("<12fH",0,0,0,*t[0],*t[1],*t[2],0) for t in tris))
        else:
            path.write_text("solid tetra\n" + "".join("facet normal 0 0 0\nouter loop\n" + "".join("vertex %s %s %s\n" % v for v in t) + "endloop\nendfacet\n" for t in tris) + "endsolid tetra\n")

    def test_ascii_and_binary_volume_and_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "shape.stl"
            for binary in (False, True):
                self.write_tetra(p, binary)
                out = inspect_stl(p, "mm")
                self.assertTrue(out["closed_edge_manifold"])
                self.assertTrue(out["consistent_winding"])
                self.assertAlmostEqual(out["volume_mm3"], 1/6)
                self.assertEqual(out["box_mm"]["size"], [1,1,1])
                self.assertEqual(out["metrics"]["extent_x"]["uncertainty"], 0.0)
                self.assertAlmostEqual(inspect_stl(p, "m")["volume_mm3"], 1e9/6)

    def test_open_mesh_does_not_claim_solid_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "shape.stl"; self.write_tetra(p, missing=True)
            out = inspect_stl(p, "mm")
            self.assertFalse(out["closed_edge_manifold"])
            self.assertIsNone(out["volume_mm3"])
            with self.assertRaises(ValueError): inspect_stl(p, "unspecified")
            p.write_text("solid broken\nvertex nan 0 0\nvertex 0 1 0\nvertex 0 0 1\nendsolid")
            with self.assertRaises(ValueError): inspect_stl(p, "mm")


def extreme_box(low, high):
    """Fake IBody2.GetExtremePoint of an axis-aligned box given in metres (part frame)."""
    def extreme(dx, dy, dz, x, y, z):
        for ref, d, a, b in ((x, dx, low[0], high[0]), (y, dy, low[1], high[1]), (z, dz, low[2], high[2])):
            ref.value = b if d > 0 else a if d < 0 else (a + b) / 2
        return True
    return extreme


class NativeAdapter(unittest.TestCase):
    def test_native_server_catalog_preserves_old_tools_and_dispatches_design(self):
        automation = types.ModuleType("solidworks_mcp.automation")
        automation.SolidWorksAutomation = lambda: types.SimpleNamespace(is_connected=False)
        com = types.ModuleType("solidworks_mcp.com")
        verification = types.ModuleType("solidworks_mcp.verification")
        path = Path(__file__).resolve().parents[1] / "server.py"
        with patch.dict(sys.modules, {"solidworks_mcp.automation": automation, "solidworks_mcp.com": com, "solidworks_mcp.verification": verification}):
            spec = importlib.util.spec_from_file_location("solidworks_mcp._server_contract_test", path)
            server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(server)
            tools = asyncio.run(server.list_tools())
            names = {t.name for t in tools}
            self.assertEqual(len(names), 52)
            self.assertTrue({"execute_python", "create_gear", "topology_optimize", "design_capture", "design_submit", "verify_model"} <= names)
            out = asyncio.run(server.call_tool("design_calculate", {"kind": "raked_panel", "inputs": {"height_mm": 150, "rake_deg": 35, "camera_length_mm": 124, "camera_depth_mm": 26}}))
            self.assertIn("SUCCESS", out[0].text)

    def test_read_only_capture_contract_and_feature_dimension_traversal(self):
        # This is a protocol double, not a live SolidWorks test.
        from solidworks_mcp.design.inspect import capture_native
        ns = types.SimpleNamespace
        def val(obj, name):
            out = getattr(obj, name)
            return out() if callable(out) else out
        def call(obj, name, *args): return getattr(obj, name)(*args)
        dimension = ns(FullName="D1@Sketch1", SystemValue=.025, GetType=lambda: 0)
        display = ns(GetDimension2=lambda index: dimension)
        traversed = []
        feature = ns(Name="Boss", GetTypeName2=lambda: "Boss", GetFirstDisplayDimension=lambda: display,
                     GetNextDisplayDimension=lambda current: traversed.append(current) or None)
        cylinder = ns(IsPlane=lambda: False, IsCylinder=lambda: True, CylinderParams=[.01,.02,.03,0,0,1,.004])
        plane = ns(IsPlane=lambda: True, PlaneParams=[0,0,1,0,0,.005])
        faces = [ns(GetSurface=lambda: cylinder, GetArea=lambda: .001), ns(GetSurface=lambda: plane, GetArea=lambda: .002)]
        circle = ns(IsLine=lambda: False, IsCircle=lambda: True)
        body = ns(Name="Body", GetFaces=lambda: faces, GetEdges=lambda: [ns(GetCurve=lambda: circle)],
                  GetExtremePoint=extreme_box((-.01, 0, -.02), (.01, .03, .02)))
        doc = ns(ConfigurationManager=ns(ActiveConfiguration=ns(Name="Default")), GetBodies2=lambda *args: [body])
        report = {"type": "part", "errors": [], "unsaved_changes": True, "mass": {"mass_kg": 1.2}, "bodies": [{}], "box_mm": {"size": [21,31,41]}}
        backend = types.ModuleType("solidworks_mcp.com")
        backend.val, backend.call, backend.features = val, call, lambda d: [feature]
        backend.byref_double = lambda value=0.0: ns(value=value)
        verification = types.ModuleType("solidworks_mcp.verification")
        verification.model_report = lambda d: deepcopy(report)
        with patch.dict(sys.modules, {"solidworks_mcp.com": backend, "solidworks_mcp.verification": verification}):
            out = capture_native(doc)
        self.assertEqual(traversed, [display])
        self.assertEqual(out["features"][0]["dimensions"][0]["system_value_si"], .025)
        self.assertEqual(out["configuration"], "Default")
        self.assertFalse(out["incomplete"])
        self.assertTrue(out["report"]["unsaved_changes"])
        self.assertEqual(out["surface_observations"][0]["faces"][0]["radius_mm"], 4)
        self.assertEqual(out["surface_observations"][0]["faces"][1]["origin_mm"], [0,0,5])
        self.assertIsNone(out["source_file_sha256"])
        metrics = out["metrics"]
        # Tight extents replace the approximate report box; every metric can satisfy a check.
        self.assertEqual([metrics["extent_" + a]["value"] for a in "xyz"], [20.0, 30.0, 40.0])
        self.assertAlmostEqual(metrics["extent_x"]["uncertainty"], 0.00052)
        self.assertAlmostEqual(metrics["mass_kg"]["uncertainty"], 5e-6 + 1e-8 * 1.2)
        self.assertEqual((metrics["rebuild_errors"]["value"], metrics["rebuild_errors"]["uncertainty"]), (0, 0))
        self.assertEqual(metrics["solid_bodies"]["value"], 1)
        self.assertTrue(all(m["uncertainty"] is not None and m["uncertainty_basis"] for m in metrics.values()))

    def test_assembly_capture_uses_component_frames_and_flags_unresolved_parts(self):
        from solidworks_mcp.design.inspect import capture_native
        ns = types.SimpleNamespace
        def val(obj, name):
            out = getattr(obj, name)
            return out() if callable(out) else out
        def call(obj, name, *args): return getattr(obj, name)(*args)
        freeform = ns(IsPlane=lambda: False, IsCylinder=lambda: False, IsCone=lambda: False, IsSphere=lambda: False, IsTorus=lambda: False)
        washer = ns(Name="Body", GetFaces=lambda: [ns(GetSurface=lambda: freeform)], GetEdges=lambda: [],
                    GetExtremePoint=extreme_box((-.016, -.016, 0), (.016, .016, .0009)))
        # Part X -> X, part Y -> -Z, part Z -> Y, origin at Y -18.78 mm (a side washer of the differential).
        rotated = ns(ArrayData=[1, 0, 0, 0, 0, -1, 0, 1, 0, 0, -.01878, 0, 1, 0, 0, 0])
        common = dict(GetPathName=lambda: "C:/x.sldprt", ReferencedConfiguration="Default", Transform2=rotated)
        washer_comp = ns(Name2="WASHER-1", IsSuppressed=lambda: False, GetBodies2=lambda kind: [washer],
                         GetTotalTransform=lambda apply: rotated, **common)
        suppressed = ns(Name2="SUPPRESSED-1", IsSuppressed=lambda: True, **common)
        lightweight = ns(Name2="LIGHT-1", IsSuppressed=lambda: False, GetBodies2=lambda kind: None, GetModelDoc2=lambda: None, **common)
        subassembly = ns(Name2="SUB-1", IsSuppressed=lambda: False, GetBodies2=lambda kind: None,
                         GetModelDoc2=lambda: ns(GetType=lambda: 2), **common)
        doc = ns(ConfigurationManager=ns(ActiveConfiguration=ns(Name="Default")),
                 GetComponents=lambda top: [washer_comp, suppressed, lightweight, subassembly])
        report = {"type": "assembly", "errors": [], "unsaved_changes": False,
                  "mass": {"mass_kg": 0.0034, "volume_mm3": 435.4, "area_mm2": 1115.14},
                  "components": {"top_level": 4, "total": 4, "suppressed": 1}, "mates": 3, "box_mm": {"size": [40, 40, 40]}}
        backend = types.ModuleType("solidworks_mcp.com")
        backend.val, backend.call, backend.features = val, call, lambda d: []
        backend.byref_double = lambda value=0.0: ns(value=value)
        verification = types.ModuleType("solidworks_mcp.verification")
        verification.model_report = lambda d: deepcopy(report)
        with patch.dict(sys.modules, {"solidworks_mcp.com": backend, "solidworks_mcp.verification": verification}):
            out = capture_native(doc)
        self.assertEqual(out["exact_box_mm"]["min"], [-16.0, -18.78, -16.0])
        self.assertEqual(out["exact_box_mm"]["max"], [16.0, -17.88, 16.0])
        metrics = out["metrics"]
        self.assertEqual([metrics["extent_" + a]["value"] for a in "xyz"], [32.0, 0.9, 32.0])
        self.assertAlmostEqual(metrics["volume_mm3"]["uncertainty"], 0.005 + 1e-4 * 435.4)    # freeform face
        self.assertEqual((metrics["mates"]["value"], metrics["suppressed_components"]["value"]), (3, 1))
        self.assertTrue(out["incomplete"])                                                     # lightweight part
        self.assertTrue(any("LIGHT-1" in issue for issue in out["extraction_issues"]))
        self.assertFalse(any("SUB-1" in issue or "SUPPRESSED-1" in issue for issue in out["extraction_issues"]))

    def test_capture_without_exact_extents_keeps_box_unusable_for_checks(self):
        from solidworks_mcp.design.inspect import _native_metrics
        ns = types.SimpleNamespace
        def val(obj, name):
            out = getattr(obj, name)
            return out() if callable(out) else out
        def call(obj, name, *args): return getattr(obj, name)(*args)
        body = ns(Name="Body", GetFaces=lambda: [], GetEdges=lambda: [], GetExtremePoint=lambda *args: False)
        doc = ns(GetBodies2=lambda *args: [body])
        issues = []
        metrics, box = _native_metrics(doc, {"type": "part", "errors": [], "box_mm": {"size": [1, 2, 3]}}, issues,
                                       val, call, lambda value=0.0: ns(value=value))
        self.assertIsNone(box)
        self.assertIsNone(metrics["extent_x"]["uncertainty"])
        self.assertTrue(any("exact extents unavailable" in issue for issue in issues))


class Batteries(unittest.TestCase):
    """Protocol doubles for the V1/V2 batteries; not a live SolidWorks test."""
    def modules(self, report, interference=None):
        ns = types.SimpleNamespace
        def val(obj, name):
            out = getattr(obj, name)
            return out() if callable(out) else out
        def call(obj, name, *args): return getattr(obj, name)(*args)
        backend = types.ModuleType("solidworks_mcp.com")
        backend.val, backend.call, backend.features = val, call, lambda d: []
        backend.byref_double = lambda value=0.0: ns(value=value)
        verification = types.ModuleType("solidworks_mcp.verification")
        verification.model_report = lambda d: deepcopy(report)
        verification.check_interference = lambda d, limit=20: deepcopy(interference or {"success": True, "count": 0, "total_volume_mm3": 0.0, "items": []})
        return patch.dict(sys.modules, {"solidworks_mcp.com": backend, "solidworks_mcp.verification": verification})

    def test_part_battery_default_and_target_rows(self):
        from solidworks_mcp.design.battery import run_battery
        ns = types.SimpleNamespace
        body = ns(Name="Body", GetFaces=lambda: [], GetEdges=lambda: [], GetExtremePoint=extreme_box((0, 0, 0), (.06, .04, .01)))
        doc = ns(GetBodies2=lambda *args: [body])
        report = {"type": "part", "document": "BRACKET", "errors": [], "unsaved_changes": False, "mass": {"mass_kg": 0.0648}, "bodies": [{}]}
        app = ns(GetDocuments=lambda: [ns(GetTitle=lambda: "BRACKET", Visible=True), ns(GetTitle=lambda: "OLD_PART", Visible=True),
                                       ns(GetTitle=lambda: "REFERENCED", Visible=False)])
        with self.modules(report):
            out = run_battery(doc, app, {"mass_kg": {"le": 0.07}, "extent_x": {"eq": 60, "tolerance": 0.01}})
            failing = run_battery(doc, app, {"mass_kg": {"op": "le", "limit": 0.06}})
            with self.assertRaises(ValueError): run_battery(doc, app, {"mass_kg": {"le": 1, "ge": 0}})
        rows = {r["check"]: r for r in out["rows"]}
        self.assertEqual(out["battery"], "V1 part")
        self.assertTrue(out["passed"])
        self.assertTrue(rows["solid_bodies"]["pass"] and rows["rebuild_errors"]["pass"] and rows["extent_x"]["pass"])
        self.assertIsNone(rows["extent_z"]["pass"])                      # recorded, not checked
        self.assertEqual(out["open_windows"], ["OLD_PART"])
        self.assertTrue(out["hints"])
        self.assertFalse(failing["passed"])
        self.assertEqual([(i["check"], i["class"]) for i in failing["issues"]], [("mass_kg", "MODEL")])

    def test_assembly_battery_allowances_constraints_and_parking(self):
        from solidworks_mcp.design.battery import run_battery
        ns = types.SimpleNamespace
        identity = ns(ArrayData=[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
        def comp(name, fixed, status, low, high):
            body = ns(Name="Body", GetFaces=lambda: [], GetEdges=lambda: [], GetExtremePoint=extreme_box(low, high))
            return ns(Name2=name, IsSuppressed=lambda: False, IsFixed=lambda: fixed, GetConstrainedStatus=lambda: status,
                      GetBodies2=lambda kind: [body], GetTotalTransform=lambda apply: identity, Transform2=identity,
                      GetPathName=lambda: "C:/x.sldprt", ReferencedConfiguration="Default")
        parts = [comp("CASE-1", True, 3, (-.03, -.03, -.03), (.03, .03, .03)),
                 comp("FD_RING-1", False, 2, (-.06, 0, -.06), (.06, .02, .06)),
                 comp("PIN-1", False, 4, (-.032, -.004, -.004), (.032, .004, .004))]
        doc = ns(GetComponents=lambda top: parts)
        report = {"type": "assembly", "document": "ASM", "errors": [], "unsaved_changes": True,
                  "mass": {"mass_kg": 1.8}, "components": {"top_level": 3, "total": 3, "suppressed": 0}, "mates": 5}
        found = {"success": True, "count": 2, "total_volume_mm3": 1.176,
                 "items": [{"components": ["CASE-1", "PIN-1"], "volume_mm3": 1.0},
                           {"components": ["FD_PINION-1", "FD_RING-1"], "volume_mm3": 0.176},
                           {"components": ["FD_RING-1", "FD_PINION-1"], "volume_mm3": 0.3}]}
        allow = [{"pair": ["FD_RING*", "FD_PINION*"], "max_mm3": 0.5, "basis": "Tredgold tooth approximation residue"}]
        with self.modules(report, found):
            out = run_battery(doc, None, {}, True, allow, parked=True)
            with self.assertRaises(ValueError): run_battery(doc, None, {}, True, [{"pair": ["A*", "B*"], "max_mm3": 1}])
        rows = {r["check"]: r for r in out["rows"]}
        self.assertEqual(out["battery"], "V2 assembly")
        self.assertEqual(rows["interference_unallowed_mm3"]["value"], 1.0)
        self.assertFalse(rows["interference_unallowed_mm3"]["pass"])
        # The two ring/pinion regions add up to 0.476 mm3, inside the 0.5 mm3 allowance for that pair.
        self.assertEqual([(p["allowed"], p["regions"], p["volume_mm3"]) for p in out["interference_pairs"]],
                         [(False, 1, 1.0), (True, 2, 0.476)])
        self.assertEqual(out["free_components"], [{"component": "FD_RING-1", "status": "under"}])
        self.assertFalse(rows["free_components"]["pass"])                  # parked: nothing may move
        self.assertEqual(out["constraint_problems"], [{"component": "PIN-1", "status": "over"}])
        self.assertEqual(rows["fixed_components"]["value"], 1)
        self.assertEqual(rows["extent_x"]["value"], 120.0)
        self.assertIn(("interference_unallowed_mm3", "ASSEMBLY"), {(i["check"], i["class"]) for i in out["issues"]})
        self.assertFalse(out["passed"])
        unavailable = {"success": False, "message": "interference detection unavailable"}
        with self.modules(report, unavailable):
            blind = run_battery(doc, None, {}, True, allow)
        self.assertFalse({r["check"]: r for r in blind["rows"]}["interference_unallowed_mm3"]["pass"])
        self.assertIn(("interference_unallowed_mm3", "METHOD"), {(i["check"], i["class"]) for i in blind["issues"]})


class Integration(TemporaryStore):
    def test_connection_is_portable_and_has_no_shell_interpolation(self):
        config = connection("codex", self.root / "a folder with spaces")
        self.assertIn("--home", config["command"])
        self.assertEqual(config["registration_argv"][5:], config["command"])
        with patch("solidworks_mcp.design.clients.shutil.which", return_value="/mock/codex"), patch("solidworks_mcp.design.clients.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="existing")
            with self.assertRaisesRegex(ValueError, "already registered"): apply_connection(config)
            self.assertEqual(run.call_count, 1)

    def test_no_mcp_tool_can_record_approval(self):
        names = [x.name for x in definitions()]
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(any("approve" in n or n == "design_review" for n in names))
        with self.assertRaises(ValueError): dispatch("design_review", {}, self.root / "db")

    def test_real_mcp_stdio_and_tool_error_recovery(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def scenario():
            async with stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "solidworks_mcp.design.mcp", "--home", str(self.root / "mcp")])) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    self.assertEqual(len((await session.list_tools()).tools), 16)
                    bad = await session.call_tool("design_status", {"project": "missing"})
                    self.assertTrue(bad.isError)
                    good = await session.call_tool("design_context", {"query": "카메라 역경사 외형"})
                    self.assertFalse(good.isError)
                    self.assertEqual(json.loads(good.content[0].text)["data"]["mode"], "quality")
        asyncio.run(scenario())

    def test_cli_lifecycle_and_bad_inputs(self):
        env = {**os.environ, "SW_DESIGN_HOME": str(self.root / "cli")}
        demo = subprocess.run([sys.executable, "-m", "solidworks_mcp", "demo", "--output", str(self.root / "cli-example")], env=env, text=True, capture_output=True)
        self.assertEqual(demo.returncode, 0, demo.stderr)
        result = json.loads(demo.stdout)
        self.assertEqual(result["status"], "awaiting_human_review")
        bad = subprocess.run([sys.executable, "-m", "solidworks_mcp", "handoff", result["project"], result["proposed_revision"]], env=env, text=True, capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stderr)["success"])
        self.assertNotIn("Traceback", bad.stderr)


if __name__ == "__main__":
    unittest.main()
