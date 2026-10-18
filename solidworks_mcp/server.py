"""
SolidWorks MCP Server
---------------------
Main MCP server entry point with all tools.

Version: 4.0.0 (Fixed for SolidWorks 2025)
Author: Samsaam Ali Baig

Fixes v4.0.0:
- execute_python now captures stdout/stderr
- FeatureExtrusion2 with correct 23 params for SW 2025
- list_features: property access instead of method calls
- extrude_sketch: proper sketch close + select before extrude
- cut_extrude: proper sketch handling
- NEW: close_sketch tool
- NEW: get_sketch_status tool for diagnostics
"""

import io
import sys
import base64
import json
import logging
import traceback
from typing import Dict
from pathlib import Path

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

# Local imports
from .automation import SolidWorksAutomation
from .constants import SwErrors
from .config import get_config, save_config
from .utils import get_solidworks_info, set_default_unit
from . import com as swcom
from . import verification
from .knowledge import kb

# Configure logging
config = get_config()
LOG_FILE = Path(__file__).parent / config.log_file

logging.basicConfig(
    level=config.get_log_level_int(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8')]
)
logger = logging.getLogger("SolidWorksMCP")

# ============================================================================
# Global Instances
# ============================================================================

sw_automation = SolidWorksAutomation()
_INSTRUCTIONS_FILE = Path(__file__).parent / "instructions.md"
SERVER_INSTRUCTIONS = _INSTRUCTIONS_FILE.read_text(encoding="utf-8") if _INSTRUCTIONS_FILE.exists() else None
server = Server("solidworks-mcp-server", instructions=SERVER_INSTRUCTIONS)


# ============================================================================
# Tool Definitions
# ============================================================================

_NUM = {"type": "number"}
_GEAR_COMMON = {
    "module": {"type": "number", "description": "normal module m_n (bevel: outer transverse module; worm: axial)"},
    "teeth": {"description": "z, or [z1, z2] for a pair", "anyOf": [{"type": "integer"}, {"type": "array", "items": {"type": "integer"}}]},
    "mate_teeth": {"type": "integer", "description": "teeth of the mating gear (pairs, bevel)"},
    "pressure_angle": {"type": "number", "default": 20},
    "helix_angle": {"type": "number", "description": "deg; helical/herringbone default 20"},
    "hand": {"type": "string", "enum": ["right", "left"], "default": "right"},
    "profile_shift": {"description": "x or [x1, x2]; default: undercut limit for small z, V-zero pair", "anyOf": [_NUM, {"type": "array", "items": _NUM}]},
    "centre_distance": {"type": "number", "description": "mm; profile shifts are computed to suit"},
    "backlash": {"type": "number", "description": "mm, circumferential for the mesh (default 0.04 m)"},
    "face_width": {"type": "number", "description": "mm (default 10 m; bevel min(R_e/3, 10 m))"},
    "spiral_angle": {"type": "number", "description": "bevel mean spiral angle, deg (spiral_bevel default 35)"},
    "shaft_angle": {"type": "number", "default": 90},
    "system": {"type": "string", "enum": ["gleason", "standard"], "default": "gleason"},
    "starts": {"type": "integer", "description": "worm starts", "default": 1},
    "diameter_quotient": {"type": "number", "description": "worm q = d1/m", "default": 10},
}
_GEAR_SCHEMA_DESIGN = {"type": "object", "required": [], "properties": dict(_GEAR_COMMON, **{
    "kind": {"type": "string", "enum": ["pair", "gear", "internal", "rack", "bevel", "planetary", "worm"], "default": "pair"},
    "internal": {"type": "boolean", "description": "pair with an internal (ring) gear 2"},
    "ratio": {"type": "number", "description": "planetary: target ratio (ring fixed, sun in, carrier out)"},
    "planets": {"type": "integer", "default": 3},
    "pitches": {"type": "integer", "description": "rack length in pitches"},
})}
_GEAR_SCHEMA_CREATE = {"type": "object", "required": ["type", "module"], "properties": dict(_GEAR_COMMON, **{
    "type": {"type": "string", "enum": ["spur", "helical", "herringbone", "internal", "rack", "bevel", "spiral_bevel",
                                        "worm", "worm_wheel", "worm_set"]},
    "build_mate": {"type": "boolean", "default": False, "description": "also build the mating gear and check the mesh"},
    "internal_mate": {"type": "boolean", "default": False, "description": "mate is a ring gear (pinion + ring)"},
    "bore": {"type": "number", "description": "mm"}, "mate_bore": {"type": "number"},
    "keyway": {"type": "boolean", "default": False, "description": "DIN 6885 hub keyway for the bore"},
    "rim_diameter": {"type": "number", "description": "internal gear outside diameter (default d_f + 6 m)"},
    "pitches": {"type": "integer", "description": "rack length in pitches", "default": 10},
    "height": {"type": "number", "description": "rack datum height above the back (default 9 m)"},
    "length": {"type": "number", "description": "worm length, mm"},
    "wheel_teeth": {"type": "integer"}, "wheel_bore": {"type": "number"},
    "save_path": {"type": "string", "description": "file or folder to save the part(s) as .SLDPRT"},
})}
_TOPOLOGY_SCHEMA = {"type": "object", "required": [], "properties": {
    "problem": {"type": "object", "description": (
        "size [Lx, Ly(, Lz)] mm; element_size or elements; thickness (2D); volume_fraction (default 0.5); "
        "supports [{edge|face|at|box, fix: 'xy'}]; loads [{at|box|edge, force: [Fx, Fy(, Fz)] N}]; "
        "keep_out / keep_in [{box|circle|sphere|cylinder}]; type stiffness|mechanism (+ output {at, direction}); "
        "material {E, nu, density}; iterations, filter_radius, penalty")},
    "tpd": {"type": "string", "description": "ToPy problem definition text or file path"},
    "job": {"type": "string", "description": "job id to poll / build"},
    "wait": {"type": "number", "default": 25, "description": "seconds to wait in this call (max 30); poll longer jobs with job"},
    "build": {"type": "boolean", "default": False, "description": "create the SolidWorks part from a finished job"},
    "thickness": {"type": "number", "description": "plate thickness for build (default: problem thickness)"},
    "max_time": {"type": "number", "default": 900, "description": "stop the optimisation after this many seconds"},
}}

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available SolidWorks tools"""
    return [
        # Connection Tools
        Tool(
            name="connect_solidworks",
            description="Connect to SolidWorks. Launches if not running.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_solidworks_info",
            description="Get SolidWorks installation information.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Document Tools
        Tool(
            name="create_new_part",
            description="Create a new part document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="create_new_assembly",
            description="Create a new assembly document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="open_document",
            description="Open an existing SolidWorks document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to file"}
                },
                "required": ["filepath"]
            }
        ),
        Tool(
            name="save_document",
            description="Save the active document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to save (optional for Save As)"}
                },
                "required": []
            }
        ),
        Tool(
            name="close_document",
            description="Close the active document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "save": {"type": "boolean", "default": False, "description": "Save before closing"}
                },
                "required": []
            }
        ),
        Tool(
            name="get_document_info",
            description="Get information about the active document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="list_open_documents",
            description="List all open documents.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Sketch Tools
        Tool(
            name="create_sketch",
            description="Create a new sketch on a plane.",
            inputSchema={
                "type": "object",
                "properties": {
                    "plane": {
                        "type": "string",
                        "enum": ["Front", "Top", "Right"],
                        "default": "Front",
                        "description": "Plane to sketch on"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="create_sketch_on_face",
            description="Create a new sketch on an existing body face (by 3D coordinates). Use for cut-extrude on faces instead of reference planes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "number", "default": 0, "description": "X coordinate on the face"},
                    "y": {"type": "number", "default": 0, "description": "Y coordinate on the face"},
                    "z": {"type": "number", "default": 0, "description": "Z coordinate on the face"},
                    "unit": {"type": "string", "description": "Unit (mm, inch, m)"}
                },
                "required": []
            }
        ),
        Tool(
            name="draw_line",
            description="Draw a line in the active sketch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x1": {"type": "number", "default": 0, "description": "Start X"},
                    "y1": {"type": "number", "default": 0, "description": "Start Y"},
                    "x2": {"type": "number", "default": 100, "description": "End X"},
                    "y2": {"type": "number", "default": 0, "description": "End Y"},
                    "unit": {"type": "string", "description": "Unit (mm, inch, m)"}
                },
                "required": []
            }
        ),
        Tool(
            name="draw_circle",
            description="Draw a circle in the active sketch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "number", "default": 0, "description": "Center X"},
                    "y": {"type": "number", "default": 0, "description": "Center Y"},
                    "radius": {"type": "number", "default": 25, "description": "Radius"},
                    "unit": {"type": "string", "description": "Unit (mm, inch, m)"}
                },
                "required": []
            }
        ),
        Tool(
            name="draw_rectangle",
            description="Draw a rectangle in the active sketch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "x1": {"type": "number", "default": -50, "description": "First corner X"},
                    "y1": {"type": "number", "default": -25, "description": "First corner Y"},
                    "x2": {"type": "number", "default": 50, "description": "Second corner X"},
                    "y2": {"type": "number", "default": 25, "description": "Second corner Y"},
                    "unit": {"type": "string", "description": "Unit (mm, inch, m)"}
                },
                "required": []
            }
        ),
        Tool(
            name="draw_arc",
            description="Draw an arc by center and angles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cx": {"type": "number", "default": 0, "description": "Center X"},
                    "cy": {"type": "number", "default": 0, "description": "Center Y"},
                    "radius": {"type": "number", "default": 25, "description": "Radius"},
                    "start_angle": {"type": "number", "default": 0, "description": "Start angle (degrees)"},
                    "end_angle": {"type": "number", "default": 90, "description": "End angle (degrees)"},
                    "unit": {"type": "string", "description": "Unit for radius"}
                },
                "required": []
            }
        ),
        Tool(
            name="draw_polygon",
            description="Draw a regular polygon.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cx": {"type": "number", "default": 0, "description": "Center X"},
                    "cy": {"type": "number", "default": 0, "description": "Center Y"},
                    "radius": {"type": "number", "default": 25, "description": "Radius"},
                    "sides": {"type": "integer", "default": 6, "description": "Number of sides (3-100)"},
                    "unit": {"type": "string", "description": "Unit"}
                },
                "required": []
            }
        ),
        
        # Feature Tools
        Tool(
            name="extrude_sketch",
            description="Extrude the active sketch (Boss-Extrude).",
            inputSchema={
                "type": "object",
                "properties": {
                    "depth": {"type": "number", "default": 10, "description": "Extrusion depth"},
                    "both_directions": {"type": "boolean", "default": False, "description": "Extrude in both directions"},
                    "unit": {"type": "string", "description": "Unit"}
                },
                "required": []
            }
        ),
        Tool(
            name="cut_extrude",
            description="Cut extrude to remove material.",
            inputSchema={
                "type": "object",
                "properties": {
                    "depth": {"type": "number", "default": 10, "description": "Cut depth"},
                    "through_all": {"type": "boolean", "default": False, "description": "Cut through all"},
                    "both_directions": {"type": "boolean", "default": False, "description": "Cut both directions"},
                    "unit": {"type": "string", "description": "Unit"}
                },
                "required": []
            }
        ),
        Tool(
            name="fillet_edges",
            description="Add fillet to selected edges.",
            inputSchema={
                "type": "object",
                "properties": {
                    "radius": {"type": "number", "default": 2, "description": "Fillet radius"},
                    "unit": {"type": "string", "description": "Unit"}
                },
                "required": []
            }
        ),
        Tool(
            name="chamfer_edges",
            description="Add chamfer to selected edges.",
            inputSchema={
                "type": "object",
                "properties": {
                    "distance": {"type": "number", "default": 2, "description": "Chamfer distance"},
                    "angle": {"type": "number", "default": 45, "description": "Chamfer angle (degrees)"},
                    "unit": {"type": "string", "description": "Unit"}
                },
                "required": []
            }
        ),
        Tool(
            name="list_features",
            description="List all features in the model.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Sketch Management Tools
        Tool(
            name="close_sketch",
            description="Close/exit the active sketch. Call this before extrude if sketch is still open.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_sketch_status",
            description="Get diagnostic info: active sketch state, sketch count, sketch names in feature tree.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Utility Tools
        Tool(
            name="set_units",
            description="Set default unit for dimensions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "enum": ["mm", "inch", "m", "cm"],
                        "description": "Default unit"
                    }
                },
                "required": ["unit"]
            }
        ),
        Tool(
            name="execute_python",
            description=("Run Python with SolidWorks API access, one modeling stage per call. Names: sw, doc, automation, "
                         "val, call, arr, strings, byref_int, byref_bool, select, plane, feats, feat, active, report, "
                         "render, store, mm, deg, math, json. print() output and the variable 'result' are returned; "
                         "render() attaches a small image. API units are metres and radians. Before a design task "
                         "read knowledge_get('agent-guide') once: build-verify loop, basis tags, token rules."),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "report": {"type": "boolean", "default": False,
                               "description": "Append the compact model report after the code runs"}
                },
                "required": ["code"]
            }
        ),

        # Verification tools (text-to-CAD loop)
        Tool(
            name="model_report",
            description=("Compact check of the active document: rebuild errors, feature summary, bodies, bounding "
                         "box (mm), volume, mass, material; assemblies: components and mates."),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="render_views",
            description=("Small labelled image of standard views of the active document (sketches/planes hidden, "
                         "user's view restored). 2x2 grid at 384 px is about 800 tokens: use at milestones."),
            inputSchema={
                "type": "object",
                "properties": {
                    "views": {"type": "array",
                              "items": {"type": "string", "enum": ["iso", "front", "back", "left", "right", "top",
                                                                   "bottom", "trimetric", "dimetric"]},
                              "default": ["iso", "front", "top", "right"]},
                    "size": {"type": "integer", "default": 384, "minimum": 128, "maximum": 768,
                             "description": "Tile size in pixels"},
                    "hide_references": {"type": "boolean", "default": True}
                },
                "required": []
            }
        ),
        Tool(
            name="export_model",
            description=("Save a copy of the active document as STEP, STL, 3MF, IGES, Parasolid (x_t), SAT, "
                         "PDF/DXF (drawings) or PNG. Default path: next to the document file."),
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {"type": "string", "default": "step"},
                    "path": {"type": "string", "description": "Output file path (optional)"}
                },
                "required": []
            }
        ),
        Tool(
            name="check_interference",
            description="Interference volumes (mm3) between components of the active assembly.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),

        # Design knowledge base
        Tool(
            name="knowledge_search",
            description=("Search the design knowledge base: gears, gear generators, topology optimization, bearings, "
                         "fasteners, fits, shafts and keys, materials, DFM, design policy, SolidWorks API recipes, "
                         "agent guide. Returns short snippets with ids (Korean or English keywords). Start every design "
                         "task with knowledge_get('agent-guide') and knowledge_get('design-policy#basis-ladder'): some "
                         "clients do not pass the server instructions on."),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="knowledge_get",
            description=("Read one knowledge section by id from knowledge_search (e.g. 'gears#spiral-bevel-gears'), "
                         "a whole topic (e.g. 'fasteners'), or 'index' for the list of topics."),
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"]
            }
        ),

        # Gears (standards based generators) and topology optimisation
        Tool(
            name="gear_design",
            description=("Gear geometry and checks without CAD (ISO 21771 / ISO 53 involute, Gleason bevel, DIN 3975 "
                         "worm). kind: pair (default), gear, internal, rack, bevel, planetary, worm. Returns "
                         "diameters, profile shifts, centre distance, contact ratio, tip clearances, mesh phases, "
                         "warnings and the basis of every default."),
            inputSchema=_GEAR_SCHEMA_DESIGN
        ),
        Tool(
            name="create_gear",
            description=("Build a gear as native SolidWorks features in a new part, then check it (volume against "
                         "the exact tooth-section area, rebuild errors, helix hand by probing). type: spur, helical, "
                         "herringbone, internal, rack, bevel, spiral_bevel, worm, worm_wheel, worm_set. "
                         "build_mate=true also builds the mating gear (opposite hand) and rolls the pair through one "
                         "pitch with a temporary-body interference check. Part frame: axis +Z, a tooth space centred "
                         "on +X at z = 0; bevel apex at the origin; racks: datum line on X, teeth toward +Y."),
            inputSchema=_GEAR_SCHEMA_CREATE
        ),
        Tool(
            name="topology_optimize",
            description=("Structural topology optimisation (SIMP; Python 3 port of ToPy): minimum compliance "
                         "(stiffness) or compliant mechanism, 2D plate or 3D. Start a job with 'problem' (spec in mm) "
                         "or 'tpd' (ToPy file text/path); it runs in the background and this call waits up to 'wait' "
                         "s. Poll with 'job'. 'build': true turns a finished 2D result into an extruded SolidWorks "
                         "plate (3D: imports the STL as a mesh solid). Returns a small preview image."),
            inputSchema=_TOPOLOGY_SCHEMA
        ),
    ]


# ============================================================================
# Result Formatter
# ============================================================================

def format_result(r: Dict) -> str:
    """Format result dictionary as readable text"""
    status = "SUCCESS" if r["success"] else "ERROR"
    lines = [f"[{status}] {r['message']}"]
    
    if not r["success"]:
        lines.append(f"Error Code: {r['error_code']} ({r['error_name']})")
    
    if r.get("data"):
        lines.append("Details: " + json.dumps(r["data"], ensure_ascii=False, separators=(",", ":"), default=str))
    
    return "\n".join(lines)


# ============================================================================
# Tool Handlers
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle MCP tool calls"""
    try:
        logger.info(f"Tool: {name}, Args: {arguments}")
        
        # Connection Tools
        if name == "connect_solidworks":
            result = sw_automation.connect()
        
        elif name == "get_solidworks_info":
            info = get_solidworks_info()
            result = {
                "success": info["found"],
                "message": f"SolidWorks {'found' if info['found'] else 'not found'}",
                "error_code": 0 if info["found"] else 105,
                "error_name": "swSuccess" if info["found"] else "swSolidWorksNotFound",
                "data": info
            }
        
        # Document Tools
        elif name == "create_new_part":
            result = sw_automation.create_new_part()
        
        elif name == "create_new_assembly":
            result = sw_automation.create_new_assembly()
        
        elif name == "open_document":
            result = sw_automation.open_document(arguments.get("filepath", ""))
        
        elif name == "save_document":
            result = sw_automation.save_document(arguments.get("filepath"))
        
        elif name == "close_document":
            result = sw_automation.close_document(arguments.get("save", False))
        
        elif name == "get_document_info":
            result = sw_automation.get_document_info()
        
        elif name == "list_open_documents":
            result = sw_automation.list_open_documents()
        
        # Sketch Tools
        elif name == "create_sketch":
            result = sw_automation.create_sketch(arguments.get("plane", "Front"))
        
        elif name == "create_sketch_on_face":
            result = sw_automation.create_sketch_on_face(
                arguments.get("x", 0),
                arguments.get("y", 0),
                arguments.get("z", 0),
                arguments.get("unit")
            )
        
        elif name == "draw_line":
            result = sw_automation.draw_line(
                arguments.get("x1", 0),
                arguments.get("y1", 0),
                arguments.get("x2", 100),
                arguments.get("y2", 0),
                arguments.get("unit")
            )
        
        elif name == "draw_circle":
            result = sw_automation.draw_circle(
                arguments.get("x", 0),
                arguments.get("y", 0),
                arguments.get("radius", 25),
                arguments.get("unit")
            )
        
        elif name == "draw_rectangle":
            result = sw_automation.draw_rectangle(
                arguments.get("x1", -50),
                arguments.get("y1", -25),
                arguments.get("x2", 50),
                arguments.get("y2", 25),
                arguments.get("unit")
            )
        
        elif name == "draw_arc":
            result = sw_automation.draw_arc_center(
                arguments.get("cx", 0),
                arguments.get("cy", 0),
                arguments.get("radius", 25),
                arguments.get("start_angle", 0),
                arguments.get("end_angle", 90),
                arguments.get("unit")
            )
        
        elif name == "draw_polygon":
            result = sw_automation.draw_polygon(
                arguments.get("cx", 0),
                arguments.get("cy", 0),
                arguments.get("radius", 25),
                arguments.get("sides", 6),
                arguments.get("unit")
            )
        
        # Feature Tools
        elif name == "extrude_sketch":
            result = sw_automation.extrude_sketch(
                arguments.get("depth", 10),
                arguments.get("both_directions", False),
                arguments.get("unit")
            )
        
        elif name == "cut_extrude":
            result = sw_automation.cut_extrude(
                arguments.get("depth", 10),
                arguments.get("through_all", False),
                arguments.get("both_directions", False),
                arguments.get("unit")
            )
        
        elif name == "fillet_edges":
            result = sw_automation.fillet_edges(
                arguments.get("radius", 2),
                arguments.get("unit")
            )
        
        elif name == "chamfer_edges":
            result = sw_automation.chamfer_edges(
                arguments.get("distance", 2),
                arguments.get("angle", 45),
                arguments.get("unit")
            )
        
        elif name == "list_features":
            result = _list_features_fixed()
        
        # Sketch Management Tools
        elif name == "close_sketch":
            result = _close_sketch_handler()
        
        elif name == "get_sketch_status":
            result = _get_sketch_status_handler()
        
        # Utility Tools
        elif name == "set_units":
            unit = arguments.get("unit", "mm")
            set_default_unit(unit)
            sw_automation._units.default_unit = unit
            result = {
                "success": True,
                "message": f"Default unit set to: {unit}",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {"unit": unit}
            }
        
        elif name == "execute_python":
            code = arguments.get("code", "")
            if not code:
                result = sw_automation._result(False, "Code is required", SwErrors.swInvalidInput)
            else:
                result = _execute_python_fixed(code, bool(arguments.get("report", False)))
        
        # Verification tools (text-to-CAD loop)
        elif name in ("model_report", "render_views", "export_model", "check_interference"):
            result = _verification_handler(name, arguments)
        
        # Design knowledge base
        elif name == "knowledge_search":
            hits = kb().search(arguments.get("query", ""), int(arguments.get("limit", 5) or 5))
            result = {"success": True, "message": f"{len(hits)} result(s); read one with knowledge_get(id)",
                      "error_code": 0, "error_name": "swSuccess", "data": {"results": hits}}
        
        elif name in ("gear_design", "create_gear"):
            result = _gear_handler(name, arguments)
        
        elif name == "topology_optimize":
            result = _topology_handler(arguments)
        
        elif name == "knowledge_get":
            entry = kb().get(arguments.get("id", ""))
            found = "error" not in entry
            text = entry.pop("text", None)
            result = {"success": found,
                      "message": text if (found and text) else entry.pop("error", "index"),
                      "error_code": 0 if found else 404,
                      "error_name": "swSuccess" if found else "NotFound",
                      "data": entry}
        
        else:
            result = sw_automation._result(False, f"Unknown tool: {name}", SwErrors.swUnknownError)
        
        logger.info(f"Result: success={result['success']}")
        images = result.pop("images", None) or []
        content = [TextContent(type="text", text=format_result(result))]
        content += [ImageContent(type="image", data=base64.b64encode(png).decode("ascii"), mimeType="image/png")
                    for png in images]
        return content
        
    except Exception as e:
        logger.error(f"Tool error: {e}\n{traceback.format_exc()}")
        return [TextContent(type="text", text=f"[ERROR] {e}")]


# ============================================================================
# FIXED: Execute Python with stdout capture
# ============================================================================

_SCRIPT_STORE = {}   # 'store' in execute_python: survives between calls while the server runs


def _script_traceback(tb: str) -> str:
    """Keep only the part of a traceback that starts in the user's script."""
    lines = tb.strip().splitlines()
    start = next((i for i, line in enumerate(lines) if 'File "<string>"' in line), None)
    keep = lines[start:] if start is not None else lines[-6:]
    return "\n".join(keep[-12:])


def _compact(value) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return str(value)


def _execute_python_fixed(code: str, with_report: bool = False) -> Dict:
    """
    Execute custom Python code with access to SolidWorks.
    Captures stdout/stderr and 'result', injects the COM helpers (com.py) and verification
    shortcuts; images from render() are returned as image content.
    """
    images = []
    try:
        if not sw_automation.is_connected:
            r = sw_automation.connect()
            if not r["success"]:
                return r
        
        import win32com.client
        import pythoncom
        import math
        import os as os_module
        
        app = sw_automation.app
        
        def active():
            return app.ActiveDoc
        
        def report(**kwargs):
            return verification.model_report(active(), **kwargs)
        
        def render(views=("iso",), size=384, hide_references=True):
            if isinstance(views, str):
                views = (views,)
            out = verification.render_views(active(), tuple(views), int(size), hide_references, app=app)
            png = out.pop("image_png", None)
            if png:
                images.append(png)
            return {k: out[k] for k in ("views", "width", "height", "approx_tokens", "failed") if k in out}
        
        exec_globals = {
            # SolidWorks objects
            'sw': app,
            'doc': app.ActiveDoc if app else None,
            'automation': sw_automation,
            # COM libraries and helpers (see com.py)
            'win32com': win32com,
            'pythoncom': pythoncom,
            'val': swcom.val, 'call': swcom.call, 'arr': swcom.arr, 'strings': swcom.strings,
            'byref_int': swcom.byref_int, 'byref_bool': swcom.byref_bool, 'NOCALL': swcom.NOCALL,
            'select': swcom.select,
            'feats': lambda d=None: swcom.features(d or active()),
            'feat': lambda feature_name, d=None: swcom.feature(d or active(), feature_name),
            'plane': lambda which, d=None: swcom.default_plane_name(d or active(), which),
            'active': active, 'report': report, 'render': render, 'store': _SCRIPT_STORE,
            'mm': 0.001, 'deg': math.pi / 180.0,
            # Standard libraries
            'math': math,
            'os': os_module,
            'json': json,
            # Result placeholder
            'result': None,
        }
        
        old_stdout, old_stderr = sys.stdout, sys.stderr
        captured_stdout, captured_stderr = io.StringIO(), io.StringIO()
        try:
            sys.stdout, sys.stderr = captured_stdout, captured_stderr
            exec(code, exec_globals)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        
        stdout_text = captured_stdout.getvalue()
        stderr_text = captured_stderr.getvalue()
        result_val = exec_globals.get('result')
        
        message_parts = []
        if stdout_text:
            message_parts.append(f"=== Output ===\n{stdout_text.rstrip()}")
        if stderr_text:
            message_parts.append(f"=== Stderr ===\n{stderr_text.rstrip()}")
        if result_val is not None:
            message_parts.append(f"=== Result ===\n{_compact(result_val)}")
        if with_report:
            message_parts.append(f"=== Report ===\n{_compact(report())}")
        if not message_parts:
            message_parts.append("Code executed successfully (no output)")
        
        # No 'data' payload: stdout/result are already in the message (avoids sending them twice)
        return {
            "success": True,
            "message": "\n\n".join(message_parts),
            "error_code": 0,
            "error_name": "swSuccess",
            "images": images,
        }
        
    except SyntaxError as e:
        return {
            "success": False,
            "message": f"Syntax error: {e}",
            "error_code": 999,
            "error_name": "swUnknownError",
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Execution error: {type(e).__name__}: {e}\n{_script_traceback(traceback.format_exc())}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "images": images,
        }


def _verification_handler(name: str, arguments: dict) -> Dict:
    """model_report / render_views / export_model / check_interference on the active document."""
    try:
        if not sw_automation.is_connected:
            r = sw_automation.connect()
            if not r["success"]:
                return r
        doc = sw_automation.app.ActiveDoc
        
        if name == "model_report":
            return {"success": True, "message": "model report", "error_code": 0, "error_name": "swSuccess",
                    "data": verification.model_report(doc)}
        
        if name == "render_views":
            views = arguments.get("views") or ["iso", "front", "top", "right"]
            if isinstance(views, str):
                views = [views]
            out = verification.render_views(doc, tuple(views), int(arguments.get("size", 384) or 384),
                                            bool(arguments.get("hide_references", True)),
                                            app=sw_automation.app)
            png = out.pop("image_png", None)
            ok = bool(out.get("success"))
            message = (f"{len(out.get('views', []))} view(s), {out.get('width')}x{out.get('height')} px, "
                       f"about {out.get('approx_tokens')} tokens") if png else \
                      (out.get("message") or out.get("note") or "no image")
            res = {"success": ok, "message": message, "error_code": 0 if ok else 999,
                   "error_name": "swSuccess" if ok else "swUnknownError",
                   "data": {k: v for k, v in out.items() if k not in ("success", "message")}}
            if png:
                res["images"] = [png]
            return res
        
        if name == "export_model":
            out = verification.export_model(doc, arguments.get("format", "step"), arguments.get("path"))
        else:
            out = verification.check_interference(doc)
        ok = bool(out.pop("success", False))
        return {"success": ok, "message": out.pop("message", name), "error_code": 0 if ok else 999,
                "error_name": "swSuccess" if ok else "swUnknownError", "data": out}
    
    except Exception as e:
        logger.error(f"{name} error: {e}\n{traceback.format_exc()}")
        return {"success": False, "message": f"{name} error: {type(e).__name__}: {e}", "error_code": 999,
                "error_name": "swUnknownError"}


# ============================================================================
# Gears and topology optimisation
# ============================================================================

def _ok(message: str, data: Dict, images=None) -> Dict:
    out = {"success": True, "message": message, "error_code": 0, "error_name": "swSuccess", "data": data}
    if images:
        out["images"] = images
    return out


def _fail(message: str) -> Dict:
    return {"success": False, "message": message, "error_code": 999, "error_name": "swUnknownError"}


def _gear_handler(name: str, arguments: dict) -> Dict:
    from .gears import api as gear_api
    try:
        if name == "gear_design":
            return _ok("gear design", gear_api.design(arguments))
        if not sw_automation.is_connected:
            r = sw_automation.connect()
            if not r["success"]:
                return r
        data = gear_api.create(sw_automation.app, arguments)
        return _ok("gear built: %s" % (data.get("document") or "parts and mesh check"), data)
    except Exception as e:
        logger.error(f"{name} error: {e}\n{traceback.format_exc()}")
        return _fail(f"{name} error: {type(e).__name__}: {e}")


_TOPO_DIR = Path(__import__("tempfile").gettempdir()) / "solidworks_mcp" / "topopt"


def _topology_handler(arguments: dict) -> Dict:
    import subprocess
    import time
    import uuid
    try:
        job_id = arguments.get("job")
        if not job_id:
            spec, tpd = arguments.get("problem"), arguments.get("tpd")
            if not spec and not tpd:
                return _fail("give 'problem' (spec), 'tpd' or 'job'")
            if tpd and len(tpd) < 400 and Path(tpd).is_file():
                tpd = Path(tpd).read_text(encoding="utf-8-sig")
            job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
            job = _TOPO_DIR / job_id
            job.mkdir(parents=True, exist_ok=True)
            req = {"spec": spec} if spec else {"tpd": tpd}
            req["max_time"] = float(arguments.get("max_time", 900))
            (job / "problem.json").write_text(json.dumps(req), encoding="utf-8")
            log = open(job / "run.log", "wb")
            subprocess.Popen([sys.executable, "-m", "solidworks_mcp.topopt.run", str(job)],
                             cwd=str(Path(__file__).resolve().parent.parent), stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        job = _TOPO_DIR / job_id
        if not job.is_dir():
            return _fail(f"unknown job {job_id}")
        wait = min(float(arguments.get("wait", 25) or 0), 30.0)     # stay well inside client time-outs
        t0 = time.time()

        def read(name):
            f = job / name
            try:
                return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            except ValueError:
                return None
        status = read("status.json") or {"state": "starting"}
        while status.get("state") not in ("done", "error") and time.time() - t0 < wait:
            time.sleep(0.5)
            status = read("status.json") or status
        state = status.get("state")
        data = {"job": job_id, "state": state, "folder": str(job)}
        if state == "error":
            return {"success": False, "message": f"optimisation failed: {status.get('error')}", "error_code": 999,
                    "error_name": "swUnknownError", "data": data}
        if state != "done":
            data["progress"] = read("progress.json")
            return _ok("running: poll again with job=%s" % job_id, data)
        result = read("result.json") or {}
        data.update({k: result.get(k) for k in ("summary", "physical", "cad", "grey_fraction")})
        meta = result.get("meta") or {}
        data["grid"] = {"elements": meta.get("n"), "element_size": meta.get("h"), "size": meta.get("size")}
        images = []
        prev = job / "preview.png"
        if prev.exists():
            images.append(prev.read_bytes())
        if arguments.get("build"):
            if not sw_automation.is_connected:
                r = sw_automation.connect()
                if not r["success"]:
                    return r
            from .topopt import cad
            if meta.get("dim") == 2:
                loops = json.loads((job / "loops.json").read_text(encoding="utf-8"))
                thick = float(arguments.get("thickness") or meta.get("thickness") or meta.get("h") or 1.0)
                data["part"] = cad.build_plate(sw_automation.app, loops, thick, spacing=float(meta.get("h") or 1.0))
            else:
                data["part"] = cad.import_stl(sw_automation.app, str(job / "result.stl"))
        return _ok("topology optimisation done" + (" and part built" if arguments.get("build") else ""), data, images)
    except Exception as e:
        logger.error(f"topology_optimize error: {e}\n{traceback.format_exc()}")
        return _fail(f"topology_optimize error: {type(e).__name__}: {e}")


# ============================================================================
# FIXED: list_features
# ============================================================================

def _list_features_fixed() -> Dict:
    """
    List all features in the active document.
    FIXED v4.1: Property access for SW 2025 (FirstFeature, GetNextFeature, GetTypeName2).
    """
    try:
        doc, err = sw_automation.get_active_doc()
        if err:
            return err
        
        features = []
        
        # FIXED: FirstFeature is a property in SW 2025 COM, not a method
        try:
            feat = doc.FirstFeature
        except AttributeError:
            feat = doc.FirstFeature()
        
        while feat is not None:
            try:
                name = ""
                feat_type = ""
                suppressed = False
                
                try:
                    name = feat.Name
                except:
                    name = "<unknown>"
                
                # FIXED: GetTypeName2 is a property in SW 2025 COM
                try:
                    feat_type = feat.GetTypeName2
                    if callable(feat_type):
                        feat_type = feat_type()
                except:
                    try:
                        feat_type = feat.GetTypeName()
                    except:
                        feat_type = "<unknown>"
                
                try:
                    suppressed = sw_automation._com_value(feat, "IsSuppressed")
                except:
                    suppressed = False
                
                features.append({
                    "name": name,
                    "type": feat_type,
                    "suppressed": bool(suppressed)
                })
                
            except Exception as e:
                features.append({
                    "name": "<error>",
                    "type": str(e),
                    "suppressed": False
                })
            
            # FIXED: GetNextFeature is a property in SW 2025 COM
            try:
                # (a COM object is itself callable, so the old callable() check broke here)
                feat = sw_automation._com_value(feat, "GetNextFeature")
            except:
                break
        
        return {
            "success": True,
            "message": f"{len(features)} features found",
            "error_code": 0,
            "error_name": "swSuccess",
            "data": {"features": features, "count": len(features)}
        }
        
    except Exception as e:
        logger.error(f"List features error: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Error: {e}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "data": {}
        }

# ============================================================================
# NEW: close_sketch handler
# ============================================================================

def _close_sketch_handler() -> Dict:
    """
    Close the active sketch if one is open.
    Returns sketch status info.
    """
    try:
        doc, err = sw_automation.get_active_doc()
        if err:
            return err
        
        # Check if sketch is active
        had_active = False
        try:
            active_sketch = doc.SketchManager.ActiveSketch
            had_active = active_sketch is not None
        except:
            pass
        
        if had_active:
            try:
                doc.SketchManager.InsertSketch(True)
            except:
                try:
                    doc.InsertSketch2(True)
                except:
                    pass
            
            return {
                "success": True,
                "message": "Sketch closed successfully",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {"had_active_sketch": True, "action": "closed"}
            }
        else:
            return {
                "success": True,
                "message": "No active sketch to close",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {"had_active_sketch": False, "action": "none"}
            }
        
    except Exception as e:
        logger.error(f"Close sketch error: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Error: {e}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "data": {"traceback": traceback.format_exc()}
        }


# ============================================================================
# NEW: get_sketch_status handler
# ============================================================================

def _get_sketch_status_handler() -> Dict:
    """
    Get diagnostic info about the current sketch state.
    Useful for debugging sketch/extrude issues.
    """
    try:
        doc, err = sw_automation.get_active_doc()
        if err:
            return err
        
        info = {
            "has_active_sketch": False,
            "active_sketch_name": None,
            "sketch_count": 0,
            "sketch_names": [],
            "feature_count": 0,
            "extrusion_count": 0,
        }
        
        # Check active sketch
        try:
            active_sketch = doc.SketchManager.ActiveSketch
            if active_sketch is not None:
                info["has_active_sketch"] = True
                try:
                    info["active_sketch_name"] = active_sketch.Name
                except:
                    info["active_sketch_name"] = "<unknown>"
        except:
            pass
        
        # Walk feature tree (using PROPERTIES not methods)
        try:
            feat = doc.FirstFeature
            while feat is not None:
                try:
                    feat_type = feat.GetTypeName2
                    info["feature_count"] += 1
                    
                    if feat_type == "ProfileFeature":
                        info["sketch_count"] += 1
                        info["sketch_names"].append(feat.Name)
                    elif feat_type == "Extrusion":
                        info["extrusion_count"] += 1
                except:
                    pass
                try:
                    feat = feat.GetNextFeature
                except:
                    break
        except:
            pass
        
        # Build readable message
        status = "OPEN" if info["has_active_sketch"] else "CLOSED"
        msg = (f"Sketch status: {status}. "
               f"Sketches: {info['sketch_count']} {info['sketch_names']}. "
               f"Extrusions: {info['extrusion_count']}. "
               f"Total features: {info['feature_count']}")
        
        return {
            "success": True,
            "message": msg,
            "error_code": 0,
            "error_name": "swSuccess",
            "data": info
        }
        
    except Exception as e:
        logger.error(f"Sketch status error: {e}\n{traceback.format_exc()}")
        return {
            "success": False,
            "message": f"Error: {e}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "data": {"traceback": traceback.format_exc()}
        }


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for MCP server"""
    logger.info("Starting SolidWorks MCP Server v4.0.0 (Fixed)...")
    logger.info(f"Log file: {LOG_FILE}")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Run the server"""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    run()
