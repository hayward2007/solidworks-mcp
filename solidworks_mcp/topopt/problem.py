"""Topology optimisation problems: ToPy problem definition (TPD v2007) files and a
geometric specification in millimetres.

The TPD reader follows ToPy's parser (c) William Hunter, MIT License (see LICENSE_TOPY.md):
node numbers are 1-based, column-major from the top-left corner (y down), elements likewise.

Geometric spec (all lengths in mm, origin at the lower-left(-back) corner, y up):
{
  "size": [Lx, Ly] or [Lx, Ly, Lz],     domain; 2D = plane stress plate
  "element_size": h | "elements": [nx, ...],   default about 6000 (2D) / 8000 (3D) elements
  "thickness": t,                        2D plate thickness (CAD and physical units)
  "volume_fraction": 0.5,                [neutral 1:1] if not given
  "filter_radius": 1.5,                  elements [heur Sigmund 99-line / ToPy]; or "filter_radius_mm"
  "penalty": 3, "iterations": 60, "change_stop": 0.01, "eta": 0.5, "element_type": "Q4"/"Q5B"/"H8"/...
  "supports": [{"edge"|"face"|"at"|"box": ..., "fix": "xy"}],
  "loads":    [{"at"|"box"|"edge"|"face": ..., "force": [Fx, Fy(, Fz)]}],   N, split over the nodes
  "keep_out": [{"box": [...]} | {"circle": [cx, cy, r]} | {"sphere": [cx, cy, cz, r]} |
               {"cylinder": {"center": [x, y, z], "axis": "z", "radius": r}}],      void (passive)
  "keep_in":  [... same shapes ...],                                               solid (active)
  "type": "stiffness" | "mechanism" | "thermal" | "stiffness+thermal",
                                         mechanism: "output": {"at"|"box": ..., "direction": [dx, dy(, dz)]}
  "material": {"E": MPa, "nu": 0.3, "yield": MPa, "density": g/cm3, "k": W/(m K)}
  "safety_factor": 2,                    design value = factor x maximum force and heat; >= 2 (physics.py)
  "interfaces": [{"type": "bolt"|"tapped"|"pin"|"pad", "at": [x, y(, z)], "size": 5, "role": "support"|"load",
                  "force": [N], "heat_W": W, "sink": true, "grade": "8.8", "axis": "z", "length": mm}],
                                         holes and keep-in rings sized by the standards and the factor
  "critical": [{"box"|"circle"|...: ..., "reason": "..."}],                       solid, never removed
  "thermal": {"reference_C": 40, "max_temperature_C": 85, "sources": [{sel, "power_W": W}],
              "sinks": [{sel}], "convection": [{sel or "boundary": "all", "h_W_m2K": 10}],
              "plate_faces": {"h_W_m2K": 10, "sides": 2}},                          2D plate faces only
  "objective": {"stiffness": 1, "thermal": 1}    weights of the normalised compliances
}
Loads and heat are maximum service values; the solver uses factor x maximum ("design" values).
Edges (2D): left, right, bottom, top. Faces (3D): x0, x1, y0, y1, z0, z1 (also left/right/bottom/top/back/front).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

from . import physics
from .elements import element_matrix

HEADER = "[ToPy Problem Definition File v2007]"


# ----------------------------------------------------------------------------------------
# TPD files
# ----------------------------------------------------------------------------------------
def _tpd2vec(seq, dtype=float) -> np.ndarray:
    """'1|13|4; 20; 25|28' -> 1 5 9 13 20 25 26 27 28; '1.2@3' -> 1.2 1.2 1.2 (ToPy syntax)."""
    out = np.array([], dtype)
    if seq is None:
        return out
    for s in str(seq).split(";"):
        s = s.strip()
        if not s:
            continue
        if "|" in s:
            v = [dtype(x) for x in s.split("|")]
            v[1] += 1
            vec = np.arange(*v)
        elif "@" in s:
            value, num = s.split("@")
            vec = np.ones(int(num)) * dtype(value)
        else:
            vec = np.array([dtype(s)])
        out = np.append(out, vec)
    return out


def _dofvec(x, y, z, dofpn) -> np.ndarray:
    vx, vy, vz = _tpd2vec(x), _tpd2vec(y), _tpd2vec(z)
    parts = [(vx - 1) * dofpn, (vy - 1) * dofpn + 1]
    if dofpn == 3:
        parts.append((vz - 1) * dofpn + 2)
    return np.r_[tuple(parts)].astype(int)


def _valvec(x, y, z) -> np.ndarray:
    return np.r_[_tpd2vec(x), _tpd2vec(y), _tpd2vec(z)]


def parse_tpd(text: str) -> Dict:
    """ToPy problem definition text -> problem dictionary for Topology."""
    text = text.lstrip("﻿")
    if not text.startswith(HEADER):
        raise ValueError("not a ToPy v2007 problem definition (missing header)")
    d = {}
    for line in text.splitlines()[1:]:
        line = line.split("#")[0].replace("\t", "").replace(" ", "")
        if line and ":" in line:
            k, v = line.split(":", 1)
            d[k] = v
    return from_dict(d)


def from_dict(d: Dict) -> Dict:
    p = dict(d)
    p["PROB_TYPE"] = str(p["PROB_TYPE"]).lower()
    if p["PROB_TYPE"] == "heat":
        raise ValueError("heat-conduction problems are not supported (structural optimisation only)")
    for k in ("VOL_FRAC", "FILT_RAD", "P_FAC"):
        p[k] = float(p[k])
    for k in ("NUM_ELEM_X", "NUM_ELEM_Y", "NUM_ELEM_Z", "DOF_PN"):
        p[k] = int(p[k])
    p["ETA"] = str(p.get("ETA", "0.5")).lower()
    p["ELEM_TYPE"] = str(p["ELEM_K"]) if not isinstance(p["ELEM_K"], np.ndarray) else p.get("ELEM_TYPE", "Q4")
    if not isinstance(p["ELEM_K"], np.ndarray):
        p["ELEM_K"] = element_matrix(p["ELEM_TYPE"], 1.0, float(p.get("NU", 1 / 3)))
    if "NUM_ITER" in p:
        p["NUM_ITER"] = int(p["NUM_ITER"])
    elif "CHG_STOP" in p:
        p["CHG_STOP"] = float(p["CHG_STOP"])
    else:
        raise ValueError("neither NUM_ITER nor CHG_STOP was declared")
    for k in ("Q_FAC", "P_MAX", "P_INCR", "P_CON", "Q_MAX", "Q_INCR", "Q_CON"):
        if k in p:
            p[k] = float(p[k])
    for k in ("P_HOLD", "Q_HOLD"):
        if k in p:
            p[k] = int(p[k])
    for k in ("ACTV_ELEM", "PASV_ELEM"):
        v = p.get(k)
        p[k] = (_tpd2vec(v, int) - 1).astype(int) if isinstance(v, str) else np.asarray(v if v is not None else [], int)
    dofpn = p["DOF_PN"]
    if "FIX_DOF" not in p:
        p["FIX_DOF"] = _dofvec(p.get("FXTR_NODE_X"), p.get("FXTR_NODE_Y"), p.get("FXTR_NODE_Z"), dofpn)
        p["LOAD_DOF"] = _dofvec(p.get("LOAD_NODE_X"), p.get("LOAD_NODE_Y"), p.get("LOAD_NODE_Z"), dofpn)
        p["LOAD_VAL"] = _valvec(p.get("LOAD_VALU_X"), p.get("LOAD_VALU_Y"), p.get("LOAD_VALU_Z"))
        p["LOAD_DOF_OUT"] = _dofvec(p.get("LOAD_NODE_X_OUT"), p.get("LOAD_NODE_Y_OUT"), p.get("LOAD_NODE_Z_OUT"), dofpn)
        p["LOAD_VAL_OUT"] = _valvec(p.get("LOAD_VALU_X_OUT"), p.get("LOAD_VALU_Y_OUT"), p.get("LOAD_VALU_Z_OUT"))
    if len(p["LOAD_DOF"]) != len(p["LOAD_VAL"]):
        raise ValueError("load DOF and load value vectors differ in length")
    if not len(p["LOAD_DOF"]):
        raise ValueError("no loads given")
    return p


# ----------------------------------------------------------------------------------------
# geometric specification (mm)
# ----------------------------------------------------------------------------------------
class Grid:
    """Node/element numbering of a ToPy grid with mm coordinates (y up, origin at a corner)."""

    def __init__(self, n: List[int], h: float):
        self.n = n
        self.dim = len(n)
        self.h = h
        self.nx, self.ny = n[0], n[1]
        self.nz = n[2] if self.dim == 3 else 0

    def node_coords(self) -> np.ndarray:
        """(N, dim) coordinates in mm of all nodes in ToPy numbering order."""
        nx, ny, nz, h = self.nx, self.ny, self.nz, self.h
        if self.dim == 2:
            i, j = np.meshgrid(np.arange(nx + 1), np.arange(ny + 1), indexing="ij")   # j from the top
            return np.c_[i.ravel() * h, (ny - j.ravel()) * h]
        k, i, j = np.meshgrid(np.arange(nz + 1), np.arange(nx + 1), np.arange(ny + 1), indexing="ij")
        return np.c_[i.ravel() * h, (ny - j.ravel()) * h, k.ravel() * h]

    def element_centres(self) -> np.ndarray:
        """(E, dim) element centres (mm) in ToPy element numbering order (column-major)."""
        nx, ny, nz, h = self.nx, self.ny, self.nz, self.h
        if self.dim == 2:
            i, j = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
            return np.c_[(i.ravel() + 0.5) * h, (ny - j.ravel() - 0.5) * h]
        k, i, j = np.meshgrid(np.arange(nz), np.arange(nx), np.arange(ny), indexing="ij")
        return np.c_[(i.ravel() + 0.5) * h, (ny - j.ravel() - 0.5) * h, (k.ravel() + 0.5) * h]

    def size(self):
        return [v * self.h for v in self.n]


_FACE_ALIASES = {"left": "x0", "right": "x1", "bottom": "y0", "top": "y1", "back": "z0", "front": "z1"}


def _select(grid: Grid, item: Dict, coords: np.ndarray) -> np.ndarray:
    """Node indices (0-based, ToPy order) picked by 'at', 'box', 'edge'/'face'."""
    h, size = grid.h, grid.size()
    tol = 0.5 * h + 1e-9
    if "at" in item:
        p = np.asarray(item["at"], float)
        d = np.linalg.norm(coords - p[None, :], axis=1)
        return np.array([int(np.argmin(d))])
    if "box" in item or "region" in item:
        b = np.asarray(item.get("box", item.get("region")), float)
        lo, hi = b[:grid.dim], b[grid.dim:]
        m = np.all((coords >= np.minimum(lo, hi) - tol) & (coords <= np.maximum(lo, hi) + tol), axis=1)
        idx = np.nonzero(m)[0]
        if not len(idx):
            raise ValueError("box %s selects no nodes" % list(b))
        return idx
    name = str(item.get("edge", item.get("face", ""))).lower()
    name = _FACE_ALIASES.get(name, name)
    if len(name) == 2 and name[0] in "xyz" and name[1] in "01":
        ax = "xyz".index(name[0])
        if ax >= grid.dim:
            raise ValueError("face %s needs a 3D domain" % name)
        target = 0.0 if name[1] == "0" else size[ax]
        idx = np.nonzero(np.abs(coords[:, ax] - target) < 1e-6 * max(size) + 1e-9)[0]
        return idx
    raise ValueError("selection needs 'at', 'box' or 'edge'/'face': %s" % item)


def _element_nodes(grid: Grid) -> np.ndarray:
    """(E, 4|8) node ids of every element, in ToPy element order (same order as element_centres)."""
    nx, ny, nz = grid.nx, grid.ny, grid.nz
    if grid.dim == 2:
        i, j = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
        i, j = i.ravel(), j.ravel()
        return np.stack([physics.node_id(grid, i + a, j + b) for a, b in ((0, 1), (1, 1), (1, 0), (0, 0))], axis=1)
    k, i, j = np.meshgrid(np.arange(nz), np.arange(nx), np.arange(ny), indexing="ij")
    k, i, j = k.ravel(), i.ravel(), j.ravel()
    corners = [(a, b, c) for c in (0, 1) for a, b in ((0, 1), (1, 1), (1, 0), (0, 0))]
    return np.stack([physics.node_id(grid, i + a, j + b, k + c) for a, b, c in corners], axis=1)


def _physics_type(spec: Dict) -> str:
    t = str(spec.get("type", "")).lower().replace(" ", "")
    has_force = bool(spec.get("loads")) or any(i.get("force") for i in spec.get("interfaces", []))
    if not t:
        t = ("stiffness+thermal" if has_force else "thermal") if spec.get("thermal") else "stiffness"
    if t.startswith("mech"):
        return "mechanism"
    if t in ("thermal", "heat"):
        return "thermal"
    if t in ("stiffness+thermal", "thermal+stiffness", "both", "multi"):
        return "stiffness+thermal"
    if t in ("stiffness", "comp", "compliance"):
        return "stiffness"
    raise ValueError("type must be stiffness, mechanism, thermal or stiffness+thermal")


def _inside(shape: Dict, pts: np.ndarray, dim: int) -> np.ndarray:
    if "ring" in shape:                                        # 2D annulus [cx, cy, r_in, r_out]
        cx, cy, r_in, r_out = shape["ring"]
        dd = (pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2
        return (dd > r_in * r_in) & (dd <= r_out * r_out)
    if "box" in shape:
        b = np.asarray(shape["box"], float)
        lo, hi = np.minimum(b[:dim], b[dim:]), np.maximum(b[:dim], b[dim:])
        return np.all((pts >= lo) & (pts <= hi), axis=1)
    if "circle" in shape:
        cx, cy, r = shape["circle"]
        return (pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2 <= r * r
    if "sphere" in shape:
        cx, cy, cz, r = shape["sphere"]
        return ((pts - np.array([cx, cy, cz])) ** 2).sum(axis=1) <= r * r
    if "cylinder" in shape:
        c = shape["cylinder"]
        ctr = np.asarray(c["center"], float)
        ax = "xyz".index(str(c.get("axis", "z")).lower())
        other = [i for i in range(3) if i != ax]
        dd = ((pts[:, other] - ctr[other]) ** 2).sum(axis=1)
        m = dd <= float(c["radius"]) ** 2
        if c.get("inner_radius"):
            m &= dd > float(c["inner_radius"]) ** 2
        if "length" in c:
            m &= np.abs(pts[:, ax] - ctr[ax]) <= float(c["length"]) / 2
        return m
    raise ValueError("region shape must be box, circle, sphere or cylinder: %s" % shape)


def from_spec(spec: Dict) -> Tuple[Dict, Dict]:
    """Geometric spec -> (problem dictionary, metadata for exports and CAD)."""
    size = [float(v) for v in spec["size"]]
    dim = len(size)
    if dim not in (2, 3):
        raise ValueError("size must have 2 or 3 values")
    if spec.get("elements"):
        n0 = int(spec["elements"][0])
        h = size[0] / n0
    elif spec.get("element_size"):
        h = float(spec["element_size"])
    else:
        target = 6000 if dim == 2 else 8000                     # [neutral] resolution vs. run time
        h = (np.prod(size) / target) ** (1 / dim)
    n = [max(1, int(round(L / h))) for L in size]
    grid = Grid(n, h)
    coords = grid.node_coords()
    nodes_per_layer = (n[0] + 1) * (n[1] + 1)
    dofpn = dim
    mat = spec.get("material") or {}
    nu = float(mat.get("nu", 1 / 3))
    etype = str(spec.get("element_type", "Q4" if dim == 2 else "H8")).upper()
    sf = float(spec.get("safety_factor", physics.SAFETY_FACTOR))
    if not sf >= physics.SAFETY_FACTOR:
        raise ValueError("safety_factor %g is below %g: joints and critical features are designed for at least "
                         "2 x the maximum force and heat" % (sf, physics.SAFETY_FACTOR))
    ptype = _physics_type(spec)
    structural = ptype != "thermal"
    thickness = float(spec.get("thickness", h)) if dim == 2 else None
    fix = []
    sup_nodes = []
    for s in spec.get("supports", []):
        idx = _select(grid, s, coords)
        sup_nodes.extend(idx.tolist())
        for ax in str(s.get("fix", "xyz"[:dim])).lower():
            if "xyz".index(ax) < dim:
                fix.extend((idx * dofpn + "xyz".index(ax)).tolist())
    ldof, lval, load_draw = [], [], []
    for ld in spec.get("loads", []):
        idx = _select(grid, ld, coords)
        f = np.asarray(ld["force"], float) * sf                  # design load = factor x maximum
        for ax in range(dim):
            if f[ax]:
                ldof.extend((idx * dofpn + ax).tolist())
                lval.extend([f[ax] / len(idx)] * len(idx))
        load_draw.append((coords[idx].mean(axis=0).tolist(), f.tolist()))
    cen = grid.element_centres()
    enodes = _element_nodes(grid)
    joints = _interfaces(spec, grid, coords, cen, dim, h, sf, fix, sup_nodes, ldof, lval, load_draw)
    if structural and not fix:
        raise ValueError("at least one support is required")
    if structural and not ldof:
        raise ValueError("at least one non-zero load is required")
    prob = {
        "PROB_TYPE": "mech" if ptype == "mechanism" else ("heat" if ptype == "thermal" else "comp"),
        "PROB_NAME": str(spec.get("name", "topopt")),
        "VOL_FRAC": float(spec.get("volume_fraction", 0.5)),
        "P_FAC": float(spec.get("penalty", 3.0)),
        "ETA": str(spec.get("eta", "0.5")),
        "DOF_PN": dofpn,
        "NUM_ELEM_X": n[0], "NUM_ELEM_Y": n[1], "NUM_ELEM_Z": n[2] if dim == 3 else 0,
        "ELEM_TYPE": etype, "ELEM_K": element_matrix(etype, 1.0, nu),
        "NUM_ITER": int(spec.get("iterations", 60 if dim == 2 else 40)),
        "CHG_STOP": float(spec.get("change_stop", 0.01)),
        "FIX_DOF": np.asarray(sorted(set(fix)), int),
        "LOAD_DOF": np.asarray(ldof, int), "LOAD_VAL": np.asarray(lval, float),
    }
    fr = spec.get("filter_radius")
    if spec.get("filter_radius_mm"):
        fr = float(spec["filter_radius_mm"]) / h
    prob["FILT_RAD"] = float(fr if fr else 1.5)
    if spec.get("approx"):
        prob["APPROX"] = spec["approx"]
    for k in ("P_MAX", "P_HOLD", "P_INCR", "P_CON", "Q_FAC", "Q_MAX", "Q_HOLD", "Q_INCR", "Q_CON"):
        if k.lower() in spec:
            prob[k] = spec[k.lower()]
    out_draw = None
    if prob["PROB_TYPE"] == "mech":
        o = spec.get("output")
        if not o:
            raise ValueError("mechanism problems need 'output': {'at': [...], 'direction': [...]}")
        idx = _select(grid, o, coords)
        dvec = np.asarray(o["direction"], float)
        odof, oval = [], []
        for ax in range(dim):
            if dvec[ax]:
                odof.extend((idx * dofpn + ax).tolist())
                oval.extend([float(np.sign(dvec[ax]))] * len(idx))
        prob["LOAD_DOF_OUT"], prob["LOAD_VAL_OUT"] = np.asarray(odof, int), np.asarray(oval, float)
        out_draw = (coords[idx].mean(axis=0).tolist(), dvec.tolist())
    pasv = np.zeros(len(cen), bool)
    actv = np.zeros(len(cen), bool)
    for r in spec.get("keep_out", []) + joints["keep_out"]:
        pasv |= _inside(r, cen, dim)
    critical = []
    for r in spec.get("keep_in", []) + joints["keep_in"] + spec.get("critical", []):
        actv |= _inside(r, cen, dim)
    for r in spec.get("critical", []):
        critical.append({"shape": {k: v for k, v in r.items() if k != "reason"}, "reason": r.get("reason", ""),
                         "elements": int(_inside(r, cen, dim).sum())})
    thermal = None
    if ptype in ("thermal", "stiffness+thermal"):
        thermal = _thermal(spec, grid, coords, enodes, cen, dim, h, thickness, sf, mat, joints)
        actv[thermal.pop("ACTIVE")] = True                       # heat paths at sources and sinks stay solid
        prob["THERMAL"] = thermal
        weights = spec.get("objective") or {}
        ws = float(weights.get("stiffness", 1.0)) if ptype == "stiffness+thermal" else 0.0
        wt = float(weights.get("thermal", 1.0))
        if ws < 0 or wt <= 0:
            raise ValueError("objective weights must be >= 0 (stiffness) and > 0 (thermal)")
        prob["OBJ_WEIGHTS"] = (ws / (ws + wt), wt / (ws + wt))
    pasv &= ~actv
    keep_in_fraction = float(actv.mean())
    if keep_in_fraction > prob["VOL_FRAC"] + 1e-9 and prob["PROB_TYPE"] != "mech":
        raise ValueError("keep-in regions (joint rings, pads, critical features, heat paths) take %.0f %% of the domain, "
                         "above volume_fraction %g: raise volume_fraction, enlarge the domain or refine "
                         "element_size" % (100 * keep_in_fraction, prob["VOL_FRAC"]))
    prob["INTERFACES"] = joints["internal"]
    prob["SAFETY_FACTOR"] = sf
    prob["PASV_ELEM"] = np.nonzero(pasv)[0]
    prob["ACTV_ELEM"] = np.nonzero(actv)[0]
    meta = {"dim": dim, "n": n, "h": h, "size_requested": size, "size": grid.size(),
            "thickness": thickness,
            "material": mat or None, "supports_xy": coords[sorted(set(sup_nodes))].tolist(),
            "loads": load_draw, "output": out_draw, "element_type": etype,
            "keep_out": int(pasv.sum()), "keep_in": int(actv.sum()), "name": prob["PROB_NAME"],
            "keep_in_fraction": round(keep_in_fraction, 4),
            "physics": ptype, "safety_factor": sf, "safety_basis": physics.SF_BASIS,
            "interfaces": joints["meta"], "critical": critical,
            "thermal": None if thermal is None else {
                "reference_C": thermal["T_REF"], "max_temperature_C": thermal["T_LIMIT"],
                "power_design_W": round(float(thermal["Q"].sum()), 6), "sinks": int(len(thermal["FIX"])),
                "sources_xy": thermal["SOURCES_DRAW"], "sinks_xy": thermal["SINKS_DRAW"],
                "convection_patches": thermal["PATCHES"], "plate_faces": thermal["PLATE"] is not None}}
    return prob, meta


def _interfaces(spec, grid, coords, cen, dim, h, sf, fix, sup_nodes, ldof, lval, load_draw) -> Dict:
    """Bolts, tapped holes, pins and pads: hole (void) + keep-in ring sized by physics.joint_geometry,
    supports or design loads on the hole wall, thermal roles. Appends to fix / ldof / lval in place."""
    dofpn = dim
    out = {"keep_out": [], "keep_in": [], "meta": [], "internal": [], "heat": [], "sinks": []}
    size = grid.size()
    for n, item in enumerate(spec.get("interfaces", [])):
        geom = physics.joint_geometry(item, h)
        name = str(item.get("name") or "%s%d" % (geom["type"], n + 1))
        force = np.asarray(item.get("force", [0.0] * dim), float)
        if len(force) != dim:
            raise ValueError("%s: force needs %d components" % (name, dim))
        default = "load" if np.any(force) else ("thermal" if geom["type"] == "pad" else "support")
        role = str(item.get("role") or default).lower()
        if role not in ("support", "load", "thermal"):
            raise ValueError("%s: role must be support, load or thermal" % name)
        if geom["type"] == "pad":
            shape = {k: item[k] for k in ("box", "circle", "sphere", "cylinder") if k in item}
            if not shape:
                raise ValueError("%s: a pad needs a box, circle, sphere or cylinder" % name)
            out["keep_in"].append(shape)
            nodes = np.nonzero(_inside(shape, coords, dim))[0]
            if not len(nodes):
                raise ValueError("%s: the pad region contains no nodes" % name)
            centre = coords[nodes].mean(axis=0)
        else:
            centre = np.asarray(item["at"], float)
            if len(centre) != dim:
                raise ValueError("%s: 'at' needs %d coordinates" % (name, dim))
            r_hole, r_ring = geom["hole_mm"] / 2.0, geom["keep_in_radius_mm"]
            if dim == 2:
                out["keep_out"].append({"circle": [centre[0], centre[1], r_hole]})
                out["keep_in"].append({"ring": [centre[0], centre[1], r_hole, r_ring]})
                radial = np.hypot(coords[:, 0] - centre[0], coords[:, 1] - centre[1])
                along = np.ones(len(coords), bool)
            else:
                ax = "xyz".index(str(item.get("axis", "z")).lower())
                length = float(item.get("length", size[ax]))
                cyl = {"center": centre.tolist(), "axis": "xyz"[ax], "length": length}
                out["keep_out"].append({"cylinder": {**cyl, "radius": r_hole}})
                out["keep_in"].append({"cylinder": {**cyl, "radius": r_ring, "inner_radius": r_hole}})
                other = [i for i in range(3) if i != ax]
                radial = np.sqrt(((coords[:, other] - centre[other]) ** 2).sum(axis=1))
                along = np.abs(coords[:, ax] - centre[ax]) <= length / 2 + 1e-9
            # nodes on the hole wall: the first node ring outside the hole, always attached to a ring element
            nodes = np.nonzero((radial >= r_hole - 1e-9) & (radial <= r_hole + h + 1e-9) & along)[0]
            if not len(nodes):
                raise ValueError("%s: no nodes on the hole wall; refine element_size" % name)
        design = force * sf
        if role == "support":
            for ax in str(item.get("fix", "xyz"[:dim])).lower():
                if "xyz".index(ax) < dim:
                    fix.extend((nodes * dofpn + "xyz".index(ax)).tolist())
            sup_nodes.extend(nodes.tolist())
        elif role == "load":
            for ax in range(dim):
                if design[ax]:
                    ldof.extend((nodes * dofpn + ax).tolist())
                    lval.extend([design[ax] / len(nodes)] * len(nodes))
            load_draw.append((coords[nodes].mean(axis=0).tolist(), design.tolist()))
        if item.get("heat_W"):
            out["heat"].append((nodes, float(item["heat_W"]) * sf, coords[nodes].mean(axis=0).tolist()))
        if item.get("sink"):
            out["sinks"].append((nodes, coords[nodes].mean(axis=0).tolist()))
        record = {"name": name, "type": geom["type"], "role": role, "centre": [round(float(v), 4) for v in centre],
                  "force_max_N": force.tolist(), "force_design_N": design.tolist(), "heat_max_W": item.get("heat_W"),
                  "sink": bool(item.get("sink")), "wall_nodes": int(len(nodes))}
        record.update({k: v for k, v in geom.items() if k != "type"})
        out["meta"].append(record)
        out["internal"].append({"name": name, "item": dict(item), "geom": geom, "nodes": nodes, "role": role})
    return out


def _thermal(spec, grid, coords, enodes, cen, dim, h, thickness, sf, mat, joints) -> Dict:
    """Conduction with fixed boundary film and optional density-weighted plate-face film (2D).
    Temperatures are solved as theta = T - reference_C, so sinks sit at the reference temperature."""
    th = spec.get("thermal") or {}
    if not mat.get("k"):
        raise ValueError("thermal problems need material.k in W/(m K)")
    k = physics.k_mm(mat["k"])
    KE = physics.conduction_q4() * k * thickness if dim == 2 else physics.conduction_h8() * k * h
    nn = len(coords)
    q = np.zeros(nn)
    src_draw, sink_draw, chosen = [], [], np.zeros(nn, bool)
    solid = np.zeros(len(cen), bool)

    def keep_solid(item, nodes):
        """Heat paths stay solid: elements inside a box selection, else the elements touching the nodes."""
        inside = _inside({"box": item["box"]}, cen, dim) if "box" in item else np.zeros(len(cen), bool)
        if inside.any():
            solid[inside] = True
        else:
            chosen[nodes] = True
    for s in th.get("sources", []):
        nodes = _select(grid, s, coords)
        q[nodes] += float(s["power_W"]) * sf / len(nodes)
        keep_solid(s, nodes)
        src_draw.append(coords[nodes].mean(axis=0).tolist())
    for nodes, power, centre in joints["heat"]:
        q[nodes] += power / len(nodes)
        src_draw.append(centre)
    fixed = np.zeros(nn, bool)
    for s in th.get("sinks", []):
        nodes = _select(grid, s, coords)
        fixed[nodes] = True
        keep_solid(s, nodes)
        sink_draw.append(coords[nodes].mean(axis=0).tolist())
    for nodes, centre in joints["sinks"]:
        fixed[nodes] = True
        sink_draw.append(centre)
    rows, cols, vals, patches = [], [], [], 0
    for c in th.get("convection", []):
        hc = physics.h_mm(c["h_W_m2K"])
        nodes = None if str(c.get("boundary", "")).lower() == "all" else _select(grid, c, coords)
        for patch in physics.boundary_patches(grid, nodes):
            M = hc * (thickness * h * physics.LINE_MASS if dim == 2 else h * h * physics.AREA_MASS)
            p = np.asarray(patch)
            rows.append(np.repeat(p, len(p)))
            cols.append(np.tile(p, len(p)))
            vals.append(M.ravel())
            patches += 1
    plate = th.get("plate_faces")
    if plate and dim != 2:
        raise ValueError("plate_faces convection applies to 2D plates; use convection on faces in 3D")
    PLATE = (float(plate.get("sides", 2)) * physics.h_mm(plate["h_W_m2K"]) * h * h * physics.AREA_MASS) if plate else None
    if not fixed.any() and not patches and PLATE is None:
        raise ValueError("thermal problems need a sink or a convection boundary")
    if not q.any():
        raise ValueError("thermal problems need a heat source (power_W) or an interface with heat_W")
    active = np.nonzero(solid | np.isin(enodes, np.nonzero(chosen)[0]).any(axis=1))[0]
    Kc = None
    if rows:
        import scipy.sparse as sp
        Kc = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nn, nn)).tocsc()
    limit = th.get("max_temperature_C")
    return {"KE": KE, "Q": q, "FIX": np.nonzero(fixed)[0], "KCONV": Kc, "PLATE": PLATE, "NNODES": nn,
            "T_REF": float(th.get("reference_C", 20.0)), "T_LIMIT": None if limit is None else float(limit),
            "ACTIVE": active, "SOURCES_DRAW": src_draw, "SINKS_DRAW": sink_draw, "PATCHES": patches}


def to_tpd(prob: Dict) -> str:
    """Write a problem dictionary as a ToPy TPD file (for runs in ToPy itself)."""
    dofpn = prob["DOF_PN"]

    def nodes(dofs, comp):
        d = np.asarray(dofs, int)
        sel = d[d % dofpn == comp] // dofpn + 1
        return "; ".join(str(v) for v in sel)
    lines = [HEADER, "", "PROB_TYPE  : %s" % prob["PROB_TYPE"], "PROB_NAME  : %s" % prob.get("PROB_NAME", "topopt"),
             "ETA        : %s" % prob["ETA"], "DOF_PN     : %d" % dofpn, "VOL_FRAC   : %g" % prob["VOL_FRAC"],
             "FILT_RAD   : %g" % prob["FILT_RAD"], "P_FAC      : %g" % prob["P_FAC"],
             "ELEM_K     : %s" % prob.get("ELEM_TYPE", "Q4"), "NUM_ELEM_X : %d" % prob["NUM_ELEM_X"],
             "NUM_ELEM_Y : %d" % prob["NUM_ELEM_Y"], "NUM_ELEM_Z : %d" % prob["NUM_ELEM_Z"],
             "NUM_ITER   : %d" % prob.get("NUM_ITER", 60)]
    for comp, ax in enumerate("XYZ"[:dofpn]):
        fx = nodes(prob["FIX_DOF"], comp)
        if fx:
            lines.append("FXTR_NODE_%s: %s" % (ax, fx))
    ld, lv = np.asarray(prob["LOAD_DOF"], int), np.asarray(prob["LOAD_VAL"], float)
    for comp, ax in enumerate("XYZ"[:dofpn]):
        m = ld % dofpn == comp
        if m.any():
            lines.append("LOAD_NODE_%s: %s" % (ax, "; ".join(str(v) for v in ld[m] // dofpn + 1)))
            lines.append("LOAD_VALU_%s: %s" % (ax, "; ".join("%g" % v for v in lv[m])))
    for k in ("PASV_ELEM", "ACTV_ELEM"):
        e = np.asarray(prob.get(k, []), int)
        if len(e):
            lines.append("%s  : %s" % (k, "; ".join(str(v + 1) for v in e)))
    return "\n".join(lines) + "\n"
