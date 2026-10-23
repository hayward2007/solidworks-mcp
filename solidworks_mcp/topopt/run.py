"""Run one topology optimisation job in its own process:

    python -m solidworks_mcp.topopt.run JOB_DIR

JOB_DIR/problem.json holds {"spec": {...}} (geometric spec, see problem.py) or {"tpd": "..."}
plus optional "max_time" (s). The job writes status.json, progress.json and, when done,
result.json, density.npy, preview.png, loops.json (2D) or result.stl (3D).

Spec jobs end with physics.post_check at the design values (safety factor x maximum force and
heat). "volume_fraction": "auto" bisects the volume fraction for the lightest design whose
stress and temperature checks pass (joints are reported, not optimised).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from . import export, physics
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
    sf = float(meta.get("safety_factor") or 1.0)
    compliance = float(t.parts.get("structural", t.objfval)) if t.thermal else t.objfval
    out = {"compliance_Nmm": round(compliance / scale, 6),
           "load_point_displacement_mm": round(float(np.abs(disp).max()), 6),
           "load_point_displacement_at_max_load_mm": round(float(np.abs(disp).max()) / sf, 6),
           "load_basis": "design loads = %g x maximum service loads" % sf,
           "basis": "linear elastic, E = %g MPa%s" % (E, ", plane stress t = %g mm" % meta["thickness"]
                                                       if meta["dim"] == 2 else "")}
    rho = mat.get("density")
    if rho:
        vol = float(t.desvars.sum()) * meta["h"] ** 2 * (meta["thickness"] if meta["dim"] == 2 else meta["h"])
        out["mass_g"] = round(vol * float(rho) * 1e-3, 3)            # density in g/cm3 -> g
    return out


def optimise(spec, progress=None, max_time=None):
    prob, meta = from_spec(spec)
    t = Topology(prob)
    summary = t.run(progress=progress, max_time=max_time)
    return t, prob, meta, summary, physics.post_check(t, prob, meta)


def auto_volume(spec, progress=None, max_time=None):
    """Bisect the volume fraction for the lightest design whose field checks pass at the design values."""
    lo, hi = (float(v) for v in spec.get("auto_range", (0.15, 0.8)))
    steps = int(spec.get("auto_steps", 5))
    if not 0 < lo < hi <= 1:
        raise ValueError("auto_range must satisfy 0 < low < high <= 1")
    keep_in = from_spec(dict(spec, volume_fraction=hi))[1]["keep_in_fraction"]    # raises when keep-in > high
    lo = max(lo, keep_in + 0.02)                                 # leave the optimiser some freedom
    if lo >= hi:
        raise ValueError("keep-in regions take %.0f %% of the domain: raise the upper auto_range or enlarge the domain"
                         % (100 * keep_in))
    budget = None if not max_time else max_time / (steps + 1)
    history = []

    def attempt(vf):
        res = optimise(dict(spec, volume_fraction=vf), progress, budget)
        check = res[4]
        if not check["checks"]:
            raise ValueError("volume_fraction auto needs material.yield (structural) or thermal.max_temperature_C")
        history.append({"volume_fraction": round(vf, 4), "pass": check["field_checks_pass"],
                        "checks": {c["check"]: c["value"] for c in check["checks"]}})
        return res, check["field_checks_pass"]
    best, ok = attempt(hi)
    if not ok:
        return best, {"feasible": False, "history": history, "note": "fails at the upper volume fraction: enlarge the "
                      "design space, the thickness or the material; joints are listed in safety.joints"}
    a, b = lo, hi
    for _ in range(steps):
        mid = 0.5 * (a + b)
        res, ok = attempt(mid)
        if ok:
            b, best = mid, res
        else:
            a = mid
    return best, {"feasible": True, "chosen": round(b, 4), "history": history}


def run_job(job_dir: str) -> int:
    job = Path(job_dir)
    req = json.loads((job / "problem.json").read_text(encoding="utf-8"))
    status = {"state": "running", "pid": os.getpid(), "started": time.time()}
    _write(job / "status.json", status)
    try:
        t0 = time.time()

        def progress(rec):
            _write(job / "progress.json", {"iter": rec["iter"], "objective": rec["objective"],
                                          "volume": rec["volume"], "change": rec["change"],
                                          "elapsed_s": round(time.time() - t0, 1)})
        check = auto = None
        if req.get("tpd"):
            prob = parse_tpd(req["tpd"])
            meta = _tpd_meta(prob)
            t = Topology(prob)
            summary = t.run(progress=progress, max_time=req.get("max_time"))
        elif str(req["spec"].get("volume_fraction", "")).lower() == "auto":
            (t, prob, meta, summary, check), auto = auto_volume(req["spec"], progress, req.get("max_time"))
        else:
            t, prob, meta, summary, check = optimise(req["spec"], progress, req.get("max_time"))
        x = t.desvars
        np.save(job / "density.npy", x)
        (job / "preview.png").write_bytes(export.preview_png(x, meta))
        result = {"summary": summary, "meta": meta, "physical": physical(t, meta),
                  "history": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()
                               if k in ("iter", "objective", "volume", "change")} for r in t.history[-5:]],
                  "grey_fraction": round(float(((x > 0.1) & (x < 0.9)).mean()), 4),
                  "safety": check, "auto": auto}
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
