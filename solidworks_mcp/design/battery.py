"""Standard verification batteries of the design workflow: V1 part and V2 assembly (static).

Read-only on the active document: no rebuild, save, activation or edits. Every result is a row
check | value | unit | uncertainty | op | limit | margin | pass, with the same conservative margin
rule as Design Studio checks (the uncertainty is subtracted from the margin).
"""
from fnmatch import fnmatchcase
from .common import finite

OPERATORS = ("le", "ge", "eq")
CONSTRAINED = {1: "unknown", 2: "under", 3: "fully", 4: "over", 5: "no solution", 6: "invalid", 7: "autosolve off"}
PROBLEM_STATES = ("over", "no solution", "invalid")
INTERFERENCE_LIMIT = 200          # pairs listed; beyond this the unallowed sum cannot be decided
ISSUE_CLASS = {"rebuild_errors": "MODEL", "solid_bodies": "MODEL", "unresolved_components": "ASSEMBLY",
               "constraint_problems": "ASSEMBLY", "free_components": "ASSEMBLY",
               "interference_unallowed_mm3": "ASSEMBLY", "capture_issues": "METHOD"}


def row(check, metric, op=None, limit=None, tolerance=0.0):
    """Battery row from a capture-style metric {value, unit, uncertainty}; no op means record only."""
    value, unit, uncertainty = metric.get("value"), metric.get("unit"), metric.get("uncertainty")
    margin = passed = None
    if op is not None:
        if op not in OPERATORS:
            raise ValueError(f"{check}: operator must be one of {OPERATORS}")
        if value is None or uncertainty is None:
            passed = False
        else:
            delta = value - limit
            margin = ((-delta if op == "le" else delta) if op != "eq" else tolerance - abs(delta)) - uncertainty
            passed = margin >= -1e-12
    return {"check": check, "value": value, "unit": unit, "uncertainty": uncertainty, "op": op, "limit": limit,
            "tolerance": tolerance, "margin": margin, "pass": passed}


def parse_targets(targets):
    """{"mass_kg": {"le": 2.0}} or {"mass_kg": {"op": "le", "limit": 2.0, "tolerance": 0}} -> {metric: (op, limit, tol)}."""
    out = {}
    for metric, spec in (targets or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"target {metric} must be an object such as {{\"le\": 2.0}}")
        if "op" in spec:
            op, limit = spec["op"], spec.get("limit")
        else:
            ops = [key for key in spec if key in OPERATORS]
            if len(ops) != 1:
                raise ValueError(f"target {metric} needs exactly one of le, ge, eq")
            op, limit = ops[0], spec[ops[0]]
        if op not in OPERATORS:
            raise ValueError(f"target {metric}: operator must be one of {OPERATORS}")
        tolerance = finite(spec.get("tolerance", 0.0), f"{metric} tolerance")
        if tolerance < 0:
            raise ValueError(f"target {metric}: tolerance cannot be negative")
        out[metric] = (op, finite(limit, metric), tolerance)
    return out


def parse_allowances(allow):
    """Allowed interference: [{"pair": ["RING*", "PINION*"], "max_mm3": 0.5, "basis": "tooth approximation"}]."""
    out = []
    for item in allow or ():
        pair = item.get("pair") if isinstance(item, dict) else None
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or not all(isinstance(p, str) and p for p in pair):
            raise ValueError("each allowance needs pair: [pattern, pattern]")
        limit = finite(item.get("max_mm3"), "max_mm3")
        if limit < 0:
            raise ValueError("max_mm3 cannot be negative")
        basis = str(item.get("basis") or "").strip()
        if not basis:
            raise ValueError("each allowance needs a basis (intended press fit, known tooth residue, ...)")
        out.append({"pair": [pair[0], pair[1]], "max_mm3": limit, "basis": basis})
    return out


def _allowance(names, allowances):
    if len(names) != 2:
        return None
    a, b = names
    for item in allowances:
        p, q = item["pair"]
        if (fnmatchcase(a, p) and fnmatchcase(b, q)) or (fnmatchcase(a, q) and fnmatchcase(b, p)):
            return item
    return None


def _interference(doc, allowances, check_interference):
    out = check_interference(doc, limit=INTERFERENCE_LIMIT)
    if not out.get("success", True):
        undecided = row("interference_unallowed_mm3", {"value": None, "unit": "mm3", "uncertainty": None}, "le", 0.0)
        return [undecided], [], out.get("message", "interference check failed")
    # One component pair can report several interference regions: the allowance applies to their sum.
    groups = {}
    for item in out.get("items", []):
        names = list(item.get("components", []))
        group = groups.setdefault(tuple(sorted(names)), {"names": names, "volume": 0.0, "regions": 0,
                                                         "allowance": _allowance(names, allowances)})
        group["volume"] += item["volume_mm3"]
        group["regions"] += 1
    pairs, unallowed, count = [], 0.0, 0
    for group in groups.values():
        allowance = group["allowance"]
        allowed = allowance is not None and group["volume"] <= allowance["max_mm3"]
        pairs.append({"components": group["names"], "volume_mm3": round(group["volume"], 3), "regions": group["regions"],
                      "allowed": allowed, "allowance_mm3": allowance["max_mm3"] if allowance else None,
                      "basis": allowance["basis"] if allowance else None})
        if not allowed:
            unallowed += group["volume"]
            count += group["regions"]
    complete = out.get("count", len(pairs)) <= len(pairs)
    # Volumes are reported to 0.001 mm3; an exact zero (no unallowed pair) carries no uncertainty.
    unc = 0.0005 * count if complete else None
    rows = [row("interference_unallowed_mm3", {"value": round(unallowed, 3), "unit": "mm3", "uncertainty": unc}, "le", 0.0),
            row("interference_total_mm3", {"value": out.get("total_volume_mm3", 0.0), "unit": "mm3",
                                           "uncertainty": 0.0005 * out.get("count", 0)})]
    return rows, pairs, None


def _constraints(doc, val, call):
    free, problems, fixed = [], [], 0
    for comp in call(doc, "GetComponents", True) or ():
        if val(comp, "IsSuppressed"):
            continue
        if val(comp, "IsFixed"):
            fixed += 1
            continue
        try:
            state = CONSTRAINED.get(int(val(comp, "GetConstrainedStatus")), "unknown")
        except Exception:
            state = "unknown"
        if state in PROBLEM_STATES:
            problems.append({"component": comp.Name2, "status": state})
        elif state != "fully":
            free.append({"component": comp.Name2, "status": state})
    return fixed, free, problems


def _open_windows(app, title, val):
    windows = []
    for other in (val(app, "GetDocuments") or ()) if app is not None else ():
        try:
            name = val(other, "GetTitle")
            if name != title and val(other, "Visible"):
                windows.append(name)
        except Exception:
            continue
    return windows


def run_battery(doc, app=None, targets=None, interference=True, allow=None, parked=False):
    """V1 (part) or V2 (assembly static) battery on doc; returns rows, details and issue candidates."""
    from ..com import val, call, byref_double
    from ..verification import model_report, check_interference
    from .inspect import _native_metrics
    plan_targets, allowances = parse_targets(targets), parse_allowances(allow)
    if doc is None:
        return {"battery": None, "document": None, "summary": "no active document", "rows": [], "issues": [], "passed": False}
    report = model_report(doc)
    kind = report.get("type")
    if kind not in ("part", "assembly"):
        return {"battery": None, "document": report.get("document"), "summary": f"no battery for {kind} documents",
                "rows": [], "issues": [], "passed": False}
    capture_issues = []
    metrics, exact_box = _native_metrics(doc, report, capture_issues, val, call, byref_double)
    plan = {"rebuild_errors": ("eq", 0.0, 0.0)}
    if kind == "part":
        plan["solid_bodies"] = ("eq", 1.0, 0.0)
    plan.update(plan_targets)
    rows = []
    for metric, (op, limit, tolerance) in plan.items():
        entry = metrics.get(metric, {"value": None, "unit": None, "uncertainty": None})
        rows.append(row(metric, entry, op, limit, tolerance))
    rows += [row(metric, entry) for metric, entry in metrics.items() if metric not in plan]
    pairs, free, problems, fixed, method_problem = [], [], [], None, None
    if kind == "assembly":
        unresolved = sum("no resolved solid bodies" in issue for issue in capture_issues)
        rows.append(row("unresolved_components", {"value": unresolved, "unit": "1", "uncertainty": 0}, "eq", 0.0))
        fixed, free, problems = _constraints(doc, val, call)
        rows.append(row("constraint_problems", {"value": len(problems), "unit": "1", "uncertainty": 0}, "eq", 0.0))
        rows.append(row("fixed_components", {"value": fixed, "unit": "1", "uncertainty": 0}))
        rows.append(row("free_components", {"value": len(free), "unit": "1", "uncertainty": 0},
                        "eq" if parked else None, 0.0 if parked else None))
        if interference:
            more, pairs, method_problem = _interference(doc, allowances, check_interference)
            rows += more
    rows.append(row("capture_issues", {"value": len(capture_issues), "unit": "1", "uncertainty": 0}, "eq", 0.0))
    issues = []
    for r in rows:
        if r["pass"] is False and r["value"] is None:          # the check could not decide
            issues.append({"check": r["check"], "class": "METHOD",
                           "symptom": (method_problem if r["check"] == "interference_unallowed_mm3" and method_problem
                                       else f"{r['check']}: no value with uncertainty available")})
        elif r["pass"] is False:
            issues.append({"check": r["check"], "class": ISSUE_CLASS.get(r["check"], "MODEL" if kind == "part" else "ASSEMBLY"),
                           "symptom": f"{r['check']} = {r['value']} {r['unit'] or ''} against {r['op']} {r['limit']}".strip()})
    issues += [{"check": "capture", "class": "METHOD", "symptom": text} for text in capture_issues]
    issues += [{"check": "constraint_problems", "class": "ASSEMBLY", "symptom": f"{p['component']}: {p['status']}"} for p in problems]
    issues += [{"check": "interference_unallowed_mm3", "class": "ASSEMBLY",
                "symptom": f"{' / '.join(p['components'])}: {p['volume_mm3']} mm3"} for p in pairs if not p["allowed"]]
    windows = _open_windows(app, report.get("document"), val)
    checked = [r for r in rows if r["pass"] is not None]
    passed = all(r["pass"] for r in checked)
    battery = "V1 part" if kind == "part" else "V2 assembly"
    summary = f"{battery}: {sum(bool(r['pass']) for r in checked)}/{len(checked)} checks passed, {len(issues)} issue(s)"
    if windows:
        summary += f"; {len(windows)} other window(s) open"
    return {"battery": battery, "document": report.get("document"), "summary": summary, "passed": passed,
            "rows": rows, "interference_pairs": pairs, "free_components": free, "constraint_problems": problems,
            "exact_box_mm": exact_box, "unsaved_changes": report.get("unsaved_changes"),
            "open_windows": windows, "issues": issues,
            "hints": (["Close finished part windows after saving them (assembly-guide A1); never close the user's own documents."]
                      if windows else []) + (["Assembly moves on rebuild: park it before render, capture or save (assembly-guide A5)."]
                                            if free and parked else [])}
