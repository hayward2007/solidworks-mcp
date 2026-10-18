"""Run one topology optimisation job in its own process:

    python -m solidworks_mcp.topopt.run JOB_DIR

JOB_DIR/problem.json holds {"spec": {...}} (geometric spec, see problem.py) or {"tpd": "..."}
plus optional "max_time" (s). The job writes status.json, progress.json and, when done,
result.json, density.npy, preview.png, loops.json (2D) or result.stl (3D).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from . import export
from .problem import from_spec, parse_tpd
from .topology import Topology


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, default=float), encoding="utf-8")
    os.replace(tmp, path)


def _tpd_meta(prob):
    n = [prob["NUM_ELEM_X"], prob["NUM_ELEM_Y"]] + ([prob["NUM_ELEM_Z"]] if prob["NUM_ELEM_Z"] else [])
    return {"dim": len(n), "n": n, "h": 1.0, "size": [float(v) for v in n], "thickness": 1.0 if len(n) == 2 else None,
            "material": None, "supports_xy": [], "loads": [], "output": None, "element_type": prob.get("ELEM_TYPE"),
            "name": prob.get("PROB_NAME", "tpd")}


def physical(t: Topology, meta) -> dict:
    """Compliance and load-point displacement in N, mm when the material is known
    (unit elements: K_2D = E t K_unit, K_3D = E h K_unit)."""
    mat = meta.get("material") or {}
    E = mat.get("E")
    if not E or t.probtype != "comp":
        return {}
    scale = float(E) * (meta["thickness"] if meta["dim"] == 2 else meta["h"])
    ld = np.asarray(t.d["LOAD_DOF"], int)
    disp = t.u[ld] / scale
    out = {"compliance_Nmm": round(t.objfval / scale, 6),
           "load_point_displacement_mm": round(float(np.abs(disp).max()), 6),
           "basis": "linear elastic, E = %g MPa%s" % (E, ", plane stress t = %g mm" % meta["thickness"]
                                                       if meta["dim"] == 2 else "")}
    rho = mat.get("density")
    if rho:
        vol = float(t.desvars.sum()) * meta["h"] ** 2 * (meta["thickness"] if meta["dim"] == 2 else meta["h"])
        out["mass_g"] = round(vol * float(rho) * 1e-3, 3)            # density in g/cm3 -> g
    return out


def run_job(job_dir: str) -> int:
    job = Path(job_dir)
    req = json.loads((job / "problem.json").read_text(encoding="utf-8"))
    status = {"state": "running", "pid": os.getpid(), "started": time.time()}
    _write(job / "status.json", status)
    try:
        if req.get("tpd"):
            prob = parse_tpd(req["tpd"])
            meta = _tpd_meta(prob)
        else:
            prob, meta = from_spec(req["spec"])
        t = Topology(prob)
        t0 = time.time()

        def progress(rec):
            _write(job / "progress.json", {"iter": rec["iter"], "of": t.numiter, "objective": rec["objective"],
                                          "volume": rec["volume"], "change": rec["change"],
                                          "elapsed_s": round(time.time() - t0, 1)})
        summary = t.run(progress=progress, max_time=req.get("max_time"))
        x = t.desvars
        np.save(job / "density.npy", x)
        (job / "preview.png").write_bytes(export.preview_png(x, meta))
        result = {"summary": summary, "meta": meta, "physical": physical(t, meta),
                  "history": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()
                               if k in ("iter", "objective", "volume", "change")} for r in t.history[-5:]],
                  "grey_fraction": round(float(((x > 0.1) & (x < 0.9)).mean()), 4)}
        if meta["dim"] == 2:
            loops = export.contours(x, meta["h"], meta["size"])
            (job / "loops.json").write_text(json.dumps(loops), encoding="utf-8")
            area = export.loops_area(loops)
            result["cad"] = {"loops": len(loops), "holes": sum(1 for l in loops if export._area(l) < 0),
                             "area_mm2": round(area, 2), "thickness": meta["thickness"],
                             "volume_mm3": round(area * meta["thickness"], 2)}
        else:
            V, F = export.surface(x, meta["h"])
            result["cad"] = export.write_stl(str(job / "result.stl"), V, F, meta.get("name", "topopt"))
        _write(job / "result.json", result)
        status.update(state="done", finished=time.time())
    except Exception as e:                                   # reported to the agent via status.json
        status.update(state="error", error="%s: %s" % (type(e).__name__, e), traceback=traceback.format_exc()[-2000:])
    _write(job / "status.json", status)
    return 0 if status["state"] == "done" else 1


if __name__ == "__main__":
    sys.exit(run_job(sys.argv[1]))
