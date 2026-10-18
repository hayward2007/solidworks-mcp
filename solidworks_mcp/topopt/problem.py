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
  "type": "stiffness" | "mechanism",  mechanism: "output": {"at"|"box": ..., "direction": [dx, dy(, dz)]}
  "material": {"E": MPa, "nu": 0.3}   optional, for displacements in mm
}
Edges (2D): left, right, bottom, top. Faces (3D): x0, x1, y0, y1, z0, z1 (also left/right/bottom/top/back/front).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

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


def _inside(shape: Dict, pts: np.ndarray, dim: int) -> np.ndarray:
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
    fix = []
    sup_nodes = []
    for s in spec.get("supports", []):
        idx = _select(grid, s, coords)
        sup_nodes.extend(idx.tolist())
        for ax in str(s.get("fix", "xyz"[:dim])).lower():
            if "xyz".index(ax) < dim:
                fix.extend((idx * dofpn + "xyz".index(ax)).tolist())
    if not fix:
        raise ValueError("at least one support is required")
    ldof, lval, load_draw = [], [], []
    for ld in spec.get("loads", []):
        idx = _select(grid, ld, coords)
        f = np.asarray(ld["force"], float)
        for ax in range(dim):
            if f[ax]:
                ldof.extend((idx * dofpn + ax).tolist())
                lval.extend([f[ax] / len(idx)] * len(idx))
        load_draw.append((coords[idx].mean(axis=0).tolist(), f.tolist()))
    if not ldof:
        raise ValueError("at least one non-zero load is required")
    prob = {
        "PROB_TYPE": "mech" if str(spec.get("type", "stiffness")).lower().startswith("mech") else "comp",
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
    cen = grid.element_centres()
    pasv = np.zeros(len(cen), bool)
    actv = np.zeros(len(cen), bool)
    for r in spec.get("keep_out", []):
        pasv |= _inside(r, cen, dim)
    for r in spec.get("keep_in", []):
        actv |= _inside(r, cen, dim)
    pasv &= ~actv
    prob["PASV_ELEM"] = np.nonzero(pasv)[0]
    prob["ACTV_ELEM"] = np.nonzero(actv)[0]
    meta = {"dim": dim, "n": n, "h": h, "size_requested": size, "size": grid.size(),
            "thickness": float(spec.get("thickness", h)) if dim == 2 else None,
            "material": mat or None, "supports_xy": coords[sorted(set(sup_nodes))].tolist(),
            "loads": load_draw, "output": out_draw, "element_type": etype,
            "keep_out": int(pasv.sum()), "keep_in": int(actv.sum()), "name": prob["PROB_NAME"]}
    return prob, meta


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
