"""Thermal conduction with convection, stress recovery and joint sizing for the topology mode.

Units: mm, N, MPa, W and K (temperature differences). Conductivity k is given in W/(m K) and the
film coefficient in W/(m2 K); both are converted to mm here.

Safety factor rule [req, user rule 2026-10-23]: joints with other parts (bolts, tapped holes, pins,
contact or thermal pads) and critical features are designed for SAFETY_FACTOR times the maximum
force and the maximum heat load. Loads and heat in a spec are maximum service values; the solver
and every check use the design values (factor x maximum). The factor cannot be set below 2.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence

import numpy as np

SAFETY_FACTOR = 2.0
SF_BASIS = "[req] joints and critical features designed for 2 x the maximum force and heat (user rule)"

# Metric coarse threads, nominal d in mm. Values from the standards named in each comment [std].
CLEARANCE_MEDIUM = {3: 3.4, 4: 4.5, 5: 5.5, 6: 6.6, 8: 9.0, 10: 11.0, 12: 13.5, 16: 17.5}   # ISO 273 medium
TAP_DRILL = {3: 2.5, 4: 3.3, 5: 4.2, 6: 5.0, 8: 6.8, 10: 8.5, 12: 10.2, 16: 14.0}            # ISO 2306 coarse
STRESS_AREA = {3: 5.03, 4: 8.78, 5: 14.2, 6: 20.1, 8: 36.6, 10: 58.0, 12: 84.3, 16: 157.0}   # ISO 898-1, mm2
WASHER_OD = {3: 7.0, 4: 9.0, 5: 10.0, 6: 12.0, 8: 16.0, 10: 20.0, 12: 24.0, 16: 30.0}         # ISO 7089
BOLT_YIELD = {"8.8": 640.0, "10.9": 940.0, "12.9": 1100.0, "A2-70": 450.0, "A4-70": 450.0}     # ISO 898-1 / 3506-1 Rp0.2, MPa
PIN_YIELD = 1000.0            # [assume] hardened dowel pin (ISO 8734 class), shear check only
EDGE_FACTOR = 1.5             # [heur] centre-to-edge distance >= 1.5 d around fasteners
THREAD_SHEAR_FACTOR = 0.75    # [heur] internal thread shear area ~ 0.75 pi d L for coarse threads
MIN_ENGAGEMENT = 1.0          # [heur] at least 1 x d engaged; strip-before-yield usually needs more in Al


# ----------------------------------------------------------------------------------------
# thermal element matrices (unit element, k = 1) in the node order of elements.py
# ----------------------------------------------------------------------------------------
def conduction_q4() -> np.ndarray:
    """Bilinear square, nodes (-,-) (+,-) (+,+) (-,+); independent of the element size."""
    return np.array([[4, -1, -2, -1], [-1, 4, -1, -2], [-2, -1, 4, -1], [-1, -2, -1, 4]], float) / 6.0


def conduction_h8() -> np.ndarray:
    """Trilinear unit cube by 3-point Gauss quadrature (exact); multiply by k h for a cube of side h."""
    from .elements import _gauss, _SIGNS3, A, B, C
    pts, w = _gauss(3)
    s = _SIGNS3
    K = np.zeros((8, 8))
    for (x, y, z), wi in zip(pts, w):
        fx, fy, fz = (A + s[:, 0] * x), (B + s[:, 1] * y), (C + s[:, 2] * z)
        k8 = 8 * A * B * C
        G = np.vstack([s[:, 0] * fy * fz, s[:, 1] * fx * fz, s[:, 2] * fx * fy]) / k8
        K += wi * G.T @ G
    return 0.5 * (K + K.T)


AREA_MASS = np.array([[4, 2, 1, 2], [2, 4, 2, 1], [1, 2, 4, 2], [2, 1, 2, 4]], float) / 36.0   # unit square, ring order
LINE_MASS = np.array([[2, 1], [1, 2]], float) / 6.0                                         # unit length


def k_mm(k_si: float) -> float:
    return float(k_si) / 1000.0            # W/(m K) -> W/(mm K)


def h_mm(h_si: float) -> float:
    return float(h_si) * 1e-6              # W/(m2 K) -> W/(mm2 K)


# ----------------------------------------------------------------------------------------
# boundary patches of the structured grid (node numbering of problem.Grid / ToPy)
# ----------------------------------------------------------------------------------------
def node_id(grid, i, j, k=0):
    """i: x index, j: y index from the top, k: z index."""
    return j + i * (grid.ny + 1) + k * (grid.nx + 1) * (grid.ny + 1)


def boundary_patches(grid, nodes: Optional[Sequence[int]] = None) -> List[List[int]]:
    """Domain-boundary segments (2D, 2 nodes) or quads (3D, 4 nodes in ring order) whose nodes are
    all in `nodes` (all boundary patches when nodes is None)."""
    chosen = None if nodes is None else set(int(n) for n in nodes)
    nx, ny, nz = grid.nx, grid.ny, grid.nz
    out = []

    def keep(patch):
        if chosen is None or all(p in chosen for p in patch):
            out.append(patch)
    if grid.dim == 2:
        for j in range(ny):                                    # left and right edges, along y
            keep([node_id(grid, 0, j), node_id(grid, 0, j + 1)])
            keep([node_id(grid, nx, j), node_id(grid, nx, j + 1)])
        for i in range(nx):                                    # top (j = 0) and bottom (j = ny) edges
            keep([node_id(grid, i, 0), node_id(grid, i + 1, 0)])
            keep([node_id(grid, i, ny), node_id(grid, i + 1, ny)])
        return out
    for j in range(ny):
        for k in range(nz):                                    # x = 0 and x = Lx faces
            for i in (0, nx):
                keep([node_id(grid, i, j, k), node_id(grid, i, j + 1, k), node_id(grid, i, j + 1, k + 1), node_id(grid, i, j, k + 1)])
    for i in range(nx):
        for k in range(nz):                                    # y = top and bottom faces
            for j in (0, ny):
                keep([node_id(grid, i, j, k), node_id(grid, i + 1, j, k), node_id(grid, i + 1, j, k + 1), node_id(grid, i, j, k + 1)])
        for j in range(ny):                                    # z = 0 and z = Lz faces
            for k in (0, nz):
                keep([node_id(grid, i, j, k), node_id(grid, i + 1, j, k), node_id(grid, i + 1, j + 1, k), node_id(grid, i, j + 1, k)])
    return out


# ----------------------------------------------------------------------------------------
# stress recovery (screening) and joints
# ----------------------------------------------------------------------------------------
def element_stress(u_unit: np.ndarray, edof: np.ndarray, dim: int, nu: float, h: float, thickness: Optional[float]) -> np.ndarray:
    """Solid-material centroid stress (MPa) per element from a unit-E solution in N.
    2D plane stress: sigma = C B u / (t h); 3D: sigma = C B u / h^2 (E cancels)."""
    from .elements import _b2, _b3, c_plane_stress, c_solid
    if dim == 2:
        Bc, Cm, scale = _b2(0.0, 0.0), c_plane_stress(1.0, nu), 1.0 / (float(thickness) * h)
    else:
        Bc, Cm, scale = _b3(0.0, 0.0, 0.0), c_solid(1.0, nu), 1.0 / (h * h)
    ue = u_unit[edof]
    return (ue @ Bc.T @ Cm.T) * scale


def von_mises(s: np.ndarray) -> np.ndarray:
    if s.shape[1] == 3:
        sx, sy, t = s.T
        return np.sqrt(np.maximum(sx * sx - sx * sy + sy * sy + 3 * t * t, 0.0))
    sx, sy, sz, txy, tyz, tzx = s.T
    return np.sqrt(np.maximum(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3 * (txy ** 2 + tyz ** 2 + tzx ** 2), 0.0))


def _size(d) -> int:
    d = int(round(float(d)))
    if d not in STRESS_AREA:
        raise ValueError(f"fastener size M{d} not in the table (M3-M16)")
    return d


def joint_geometry(item: Dict, h: float) -> Dict:
    """Hole and keep-in radii for one interface before loads are known (geometric rules)."""
    kind = str(item.get("type", "bolt")).lower()
    if kind not in ("bolt", "tapped", "pin", "pad"):
        raise ValueError("interface type must be bolt, tapped, pin or pad")
    if kind == "pad":
        return {"type": kind}
    d = float(item["size"]) if kind == "pin" else _size(item["size"])
    if kind == "bolt":
        hole, basis = CLEARANCE_MEDIUM[int(d)], "[std] ISO 273 medium clearance"
        seat = WASHER_OD[int(d)] / 2.0
        seat_basis = "[std] ISO 7089 washer seat"
    elif kind == "tapped":
        hole, basis = TAP_DRILL[int(d)], "[std] ISO 2306 tap drill (coarse)"
        seat, seat_basis = 0.0, ""
    else:
        hole, basis = float(item.get("hole", d)), "[req] pin diameter (transition fit)"
        seat, seat_basis = 0.0, ""
    outer = max(EDGE_FACTOR * d, seat + h)            # keep at least one element of material beyond the seat
    return {"type": kind, "d": d, "hole_mm": hole, "hole_basis": basis, "keep_in_radius_mm": outer,
            "keep_in_basis": f"max([heur] {EDGE_FACTOR} d edge distance, {seat_basis + ' + 1 element' if seat else 'hole'})"}


def joint_checks(item: Dict, geom: Dict, force_design: float, thickness: float, material: Dict, sf: float) -> Dict:
    """Utilisation of one joint at the design force (N): <= 1 passes. thickness = loaded length (mm)."""
    sy = material.get("yield")
    rows = []
    if geom["type"] == "pad" or force_design <= 0:
        return {"force_design_N": round(force_design, 3), "rows": rows, "pass": True}
    d, hole, ring = geom["d"], geom["hole_mm"], geom["keep_in_radius_mm"]

    def add(name, demand, capacity, unit, basis):
        util = demand / capacity if capacity > 0 else math.inf
        rows.append({"check": name, "demand": round(demand, 3), "capacity": round(capacity, 3), "unit": unit,
                     "utilisation": round(util, 4), "pass": util <= 1.0, "basis": basis})
    if geom["type"] in ("bolt", "tapped"):
        grade = str(item.get("grade", "8.8"))
        if grade not in BOLT_YIELD:
            raise ValueError(f"bolt grade must be one of {sorted(BOLT_YIELD)}")
        ry, As = BOLT_YIELD[grade], STRESS_AREA[int(d)]
        add("bolt shear (threads in the shear plane)", force_design / As, ry / math.sqrt(3), "MPa",
            f"[std] ISO 898-1 {grade} Rp0.2 / sqrt(3), stress area {As} mm2")
        if item.get("axial"):
            add("bolt tension", force_design / As, ry, "MPa", f"[std] ISO 898-1 {grade} Rp0.2")
    else:
        add("pin shear", force_design / (math.pi * d * d / 4), PIN_YIELD / math.sqrt(3), "MPa", "[assume] hardened pin yield 1000 MPa / sqrt(3)")
    if sy:
        add("part bearing", force_design / (d * thickness), sy, "MPa", "[heur] bearing pressure <= part yield (conservative)")
        e_req = hole / 2 + force_design * math.sqrt(3) / (2 * thickness * sy)
        add("part tear-out edge distance", e_req, ring, "mm", "[calc] F <= 2 (e - hole/2) t sy/sqrt(3)")
        if geom["type"] == "tapped":
            tau = sy / math.sqrt(3)
            l_load = force_design / (tau * THREAD_SHEAR_FACTOR * math.pi * d)
            l_strip = BOLT_YIELD[str(item.get("grade", "8.8"))] * STRESS_AREA[int(d)] / (tau * THREAD_SHEAR_FACTOR * math.pi * d)
            l_req = max(l_load, l_strip, MIN_ENGAGEMENT * d)
            engaged = float(item.get("engagement", thickness))
            add("thread engagement", l_req, engaged, "mm",
                "[calc] max(design force, strip-before-bolt-yield) / (0.75 pi d sy/sqrt(3)), >= 1 d")
    return {"force_design_N": round(force_design, 3), "safety_factor": sf, "rows": rows, "pass": all(r["pass"] for r in rows)}


# ----------------------------------------------------------------------------------------
# checks at the design values
# ----------------------------------------------------------------------------------------
STRESS_BASIS = ("[calc] SIMP screening: centroid von Mises of elements with density >= 0.5, qp-relaxed (q = 0.5), "
                "excluding elements on loaded or fixed nodes (joints are checked separately); not FEA of the final CAD")
THERMAL_BASIS = "[calc] steady conduction with the given films at factor x maximum heat; nodes of elements with density >= 0.5"


def post_check(t, prob: Dict, meta: Dict) -> Dict:
    """Stress screening, every joint and the peak temperature at the design values (factor x maximum)."""
    sf = float(prob.get("SAFETY_FACTOR", SAFETY_FACTOR))
    mat = meta.get("material") or {}
    dim, h, thick = meta["dim"], meta["h"], meta.get("thickness")
    x = t.desvars.ravel()
    solid = x >= 0.5
    nodes_of = t.edof[:, ::t.dofpn] // t.dofpn
    out = {"safety_factor": sf, "basis": SF_BASIS, "checks": [], "joints": [], "issues": []}

    def check(name, value, limit, unit, basis, extra=None):
        row = {"check": name, "value": round(float(value), 4), "op": "le", "limit": round(float(limit), 4),
               "unit": unit, "pass": bool(value <= limit), "basis": basis}
        row.update(extra or {})
        out["checks"].append(row)
        if not row["pass"]:
            out["issues"].append({"class": "MODEL", "check": name,
                                  "symptom": "%s = %.4g %s above %.4g %s" % (name, value, unit, limit, unit)})
    if t.has_struct and t.probtype == "comp":
        sy, nu = mat.get("yield"), float(mat.get("nu", 1 / 3))
        if not sy:
            out["issues"].append({"class": "DATA", "check": "stress_vm_design_MPa",
                                  "symptom": "material.yield missing: no stress check at the design load"})
        else:
            vm = von_mises(element_stress(t.u, t.edof, dim, nu, h, thick)) * np.sqrt(np.clip(x, 0.0, 1.0))
            touched = np.unique(np.r_[np.asarray(prob["LOAD_DOF"], int) // t.dofpn, t.fixdof // t.dofpn])
            keep = solid & ~np.isin(nodes_of, touched).any(axis=1)
            if keep.any():
                i = int(np.argmax(np.where(keep, vm, -1.0)))
                vmax = float(vm[i])
                check("stress_vm_design_MPa", vmax, float(sy), "MPa", STRESS_BASIS,
                      {"p99_MPa": round(float(np.percentile(vm[keep], 99)), 3),
                       "sf_at_max_load": round(sf * float(sy) / vmax, 3) if vmax > 0 else None,
                       "element": i})
        reaction = t.stiffness() @ t.u - t.r
        for joint in prob.get("INTERFACES", []):
            if joint["role"] == "support":
                vec = [float(reaction[joint["nodes"] * t.dofpn + a].sum()) for a in range(dim)]
            elif joint["role"] == "load":
                vec = (np.asarray(joint["item"].get("force"), float) * sf).tolist()
            else:
                continue
            force = float(np.linalg.norm(vec))
            length = thick if dim == 2 else float(joint["item"].get("thickness", joint["item"].get("length", h)))
            res = joint_checks(joint["item"], joint["geom"], force, length, mat, sf)
            out["joints"].append({"name": joint["name"], "type": joint["geom"]["type"], "role": joint["role"],
                                  "force_design_vector_N": [round(v, 3) for v in vec], **res})
            for row in res["rows"]:
                if not row["pass"]:
                    out["issues"].append({"class": "SPEC", "check": "%s: %s" % (joint["name"], row["check"]),
                                          "symptom": "utilisation %.3g at the design force %.4g N" % (row["utilisation"], force)})
    if t.thermal:
        th = prob["THERMAL"]
        hot = np.unique(nodes_of[solid]) if solid.any() else np.arange(len(t.theta))
        theta = float(t.theta[hot].max())
        out["thermal"] = {"reference_C": th["T_REF"], "max_design_C": round(th["T_REF"] + theta, 3),
                          "max_at_max_heat_C": round(th["T_REF"] + theta / sf, 3), "basis": THERMAL_BASIS}
        if th.get("T_LIMIT") is None:
            out["issues"].append({"class": "DATA", "check": "temperature_max_design_C",
                                  "symptom": "thermal.max_temperature_C missing: no temperature check"})
        else:
            check("temperature_max_design_C", th["T_REF"] + theta, th["T_LIMIT"], "C", THERMAL_BASIS,
                  {"at_max_heat_C": round(th["T_REF"] + theta / sf, 3)})
    out["field_checks_pass"] = bool(out["checks"]) and all(c["pass"] for c in out["checks"])
    out["pass"] = out["field_checks_pass"] and all(j["pass"] for j in out["joints"]) and \
        not any(i["class"] == "DATA" for i in out["issues"])
    return out
