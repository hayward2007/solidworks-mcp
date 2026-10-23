"""Self-contained, escaped review exports with preserved evidence attachments."""
import base64
import html
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from .common import encoded, digest, write_new
from .engine import Engine


def export_review(store, project, revision, output):
    rev = store.revision(project, revision)
    p = rev["packet"]
    gate = Engine(store).evaluate(project, p)
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError(f"review destination already exists; choose a new directory: {output}")
    output.mkdir(parents=True, mode=0o700)
    esc = lambda x: html.escape(str(x), quote=True)

    def table(headers, rows):
        return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{esc(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'

    def section(title, body):
        return f'<section><h2>{esc(title)}</h2>{body}</section>'

    def pretty(value):
        return '<pre>' + esc(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + '</pre>'

    def number(value):
        return "unknown/unbounded" if value is None else format(value, ".6g")

    def details(title, value):
        return '<details><summary>' + esc(title) + '</summary>' + pretty(value) + '</details>'

    def bullets(rows, ordered=False):
        tag = "ol" if ordered else "ul"
        return f'<{tag}>' + ''.join('<li>' + esc(x) + '</li>' for x in rows) + f'</{tag}>'

    previews = []
    attachments = []
    for a in gate["artifacts"]:
        data = Path(a["stored_path"]).read_bytes()
        suffix = Path(a["original_path"]).suffix.lower()
        # Do not derive paths from user-supplied titles or execute active attachments.
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf", ".json", ".stl", ".step", ".stp", ".sldprt", ".sldasm", ".md", ".txt"}:
            suffix = ".bin"
        name = "assets/" + a["sha256"] + suffix
        write_new(output / name, data)
        attachments.append({"id": a["id"], "sha256": a["sha256"], "path": name, "media_type": a["media_type"]})
        if a["id"] in p["aesthetics"]["visual_artifact_ids"] and a["media_type"].startswith("image/"):
            uri = 'data:' + a["media_type"] + ';base64,' + base64.b64encode(data).decode("ascii")
            previews.append(f'<figure><img alt="{esc(a["id"])}" src="{uri}"><figcaption>{esc(a["id"])} · SHA-256 {esc(a["sha256"])}</figcaption></figure>')

    status = "검토 대기 · Awaiting human review" if gate["engineering_ready"] else "보완 필요 · Engineering blockers"
    body = f'<header><p class="eyebrow">DESIGN STUDIO / {esc(project)} / REV {rev["ordinal"]}</p><h1>{esc(p["title"])}</h1><p>{esc(p["summary"])}</p><p class="badge">{status}</p><p>{esc(p["stage"])} · {esc(p["usage"])} · Production certified: false</p></header>'
    body += section("01 / 검토 범위와 기준계", table(["기준", "정의"], [("원점", p["datums"]["origin"]), ("좌표축", p["datums"]["axes"]), ("길이 단위", "mm")]) + '<h3>이번 변경</h3>' + bullets(p["change_summary"]) + '<h3>보호할 인터페이스</h3>' + bullets([x["id"] + ': ' + x["description"] for x in p["protected_interfaces"]]) + details("Revision / 원본 및 증거 해시", {"revision": revision, "packet_sha256": gate["packet_hash"], "evidence_sha256": gate["evidence_hash"]}))
    labels = [("intent", "디자인 의도"), ("silhouette", "실루엣"), ("proportions", "비례"), ("edge_hierarchy", "모서리·곡률 체계"), ("split_lines", "분할·파팅라인"), ("cmf", "색·재료·마감"), ("assessment", "평가와 한계")]
    body += section("02 / 외형·형상 검토", ''.join(previews) + table(["항목", "설계 기준"], [(label, p["aesthetics"][key]) for key, label in labels]) + '<h3>시각 기준과 판단</h3>' + table(["기준", "목표", "판단"], [(c["metric"], c["target"], c["evaluation"]) for c in p["aesthetics"]["criteria"]]))
    operators = {"le": "≤", "ge": "≥", "eq": "="}
    body += section("03 / 정량 요구사항", '<p>표는 6자리 유효숫자로 표시합니다. 원본 JSON은 전체 계산값을 보존하며, 표시 자릿수가 측정 정밀도를 의미하지 않습니다.</p>' + table(["요구", "지표", "결과", "한계", "불확도", "여유", "판정"],
        [(r["requirement_id"], r["metric"], f'{number(r["value"])} {r["unit"]}', f'{operators[r["operator"]]} {number(r["limit"])} {r["unit"]}', f'{number(r["uncertainty"])} {r["unit"]}', f'{number(r["margin"])} {r["unit"]}', "PASS" if r["passed"] else "FAIL") for r in gate["checks"]]) + details("검사별 원본·조건·전체 계산값", gate["checks"]))
    body += section("04 / 치수와 근거", table(["Parameter", "Value", "Unit", "Basis", "Evidence", "Rationale"],
        [(r["id"], r["value"], r["unit"], r["basis"], ', '.join(r["evidence_ids"]), r["rationale"]) for r in p["parameters"]]))
    geometry = ''.join('<h3>' + esc(g["id"] + ' / ' + g["type"]) + '</h3>' + table(["정의", "내용"], [("기준계", g["frame"]), ("형상 구성", g["construction"]), ("검증 조건", g["acceptance"])]) for g in p["geometry"])
    body += section("05 / 형상 구성과 대안", geometry + '<h3>동일 조건의 대안 비교</h3>' + table(["대안", "설명", "정량·외형 tradeoff", "선택 이유"], [(a["id"], a["description"], a["tradeoffs"], a["why_selected_or_rejected"]) for a in p["alternatives"]]))
    m = p["manufacturing"]
    body += section("06 / 제조·조립·정비", table(["항목", "명세"], [("공정", m["process"]), ("재료", m["material"]), ("기준면", m["datum_scheme"]), ("주요 공차", m["critical_tolerances"]), ("정비 접근", m["service_access"])]) + '<h3>조립 순서</h3>' + bullets(m["assembly_sequence"], True) + '<h3>제조사 확인 사항</h3>' + bullets(m["supplier_checks"]))
    calculations = ''
    for cid, c in gate["calculations"].items():
        calculations += '<h3>' + esc(cid + ' / ' + c["kind"]) + '</h3><p>' + esc(c["assumptions"]) + '</p>'
        calculations += '<pre>' + esc('\n'.join(c["equations"])) + '</pre>'
        calculations += table(["입력", "값", "단위"], [(key, number(value), c["input_units"][key]) for key, value in c["inputs"].items()])
        calculations += table(["출력", "값", "단위"], [(key, number(value), c["output_units"][key]) for key, value in c["outputs"].items()])
    body += section("07 / 재현 가능한 계산", calculations + details("계산 입력·출력 원문", gate["calculations"]))
    body += section("08 / 미해결 항목", '<h3>자동 게이트</h3>' + bullets([x["code"] + ': ' + x["detail"] for x in gate["blockers"]] or ["현재 명세에 대한 자동 계산 게이트 통과. 사용자 검토 및 실제 제품 검증은 별도입니다."]) + '<h3>위험과 후속 검증</h3>' + table(["위험", "중요도·상태", "후속 조치"], [(r["description"], r["severity"] + ' / ' + r["status"], r["next_action"]) for r in p["risks"]]) + details("미확인 파라미터", gate["warnings"]) + bullets(gate["limits"]))
    body += section("09 / 증거 원장", table(["증거", "상태", "주장", "원본 위치·측정 조건"], [(e["id"], e["kind"], e["statement"], e["locator"]) for e in gate["evidence"]]) + details("전체 증거·원본 데이터", gate["evidence"]) + '<ul>' + ''.join(f'<li><a download href="{esc(a["path"])}">{esc(a["id"])}</a> · {esc(a["sha256"])}</li>' for a in attachments) + '</ul>')
    review_argv = [sys.executable, "-m", "solidworks_mcp", "--home", str(store.home), "review", project, revision, "--decision", "approve", "--reviewer", "NAME", "--note", "검토한 범위와 수용한 위험"]
    review_command = subprocess.list2cmdline(review_argv) if os.name == "nt" else shlex.join(review_argv)
    body += section("10 / 사용자 검토", '<p>수치·좌표계·가정과 모든 시각 자료를 확인하고, 선택한 대안 및 수정 사항을 검토 기록에 남기세요. 이 파일을 열거나 계산을 통과하는 것만으로 승인되지 않습니다. 아래 명령은 검토자가 직접 기록할 때 사용하며 에이전트가 대신 실행하면 안 됩니다.</p><pre>' + esc(review_command) + '</pre>')
    css = """*{box-sizing:border-box}body{margin:0;background:#eceeea;color:#1d2927;font:15px/1.65 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:48px 28px}header{padding:40px;background:#163d34;color:#f8f6e9;border-radius:16px}.eyebrow{letter-spacing:.16em;font-size:12px}h1{font-size:34px;line-height:1.25;margin:16px 0}h2{font-size:21px;margin:0 0 20px}.badge{display:inline-block;background:#eddb9e;color:#302c19;padding:6px 14px;border-radius:30px}section{background:#fff;padding:30px;margin-top:22px;border:1px solid #d6dfda;border-radius:12px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:12px;border-bottom:1px solid #dce4df;text-align:left;vertical-align:top;min-width:70px}th{background:#f1f5f2}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f4;padding:18px;font:12px/1.6 ui-monospace,monospace}figure{margin:0 0 24px}img{width:100%;max-height:700px;object-fit:contain;background:#f7f8f5}figcaption{font:11px/1.5 ui-monospace,monospace;overflow-wrap:anywhere}a{color:#12624d}@media(max-width:600px){main{padding:16px 10px}section,header{padding:20px}h1{font-size:26px}}@media print{body{background:white}section{break-inside:avoid}main{padding:0}}"""
    document = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; img-src data:; style-src &#39;unsafe-inline&#39;"><title>' + esc(p["title"]) + '</title><style>' + css + '</style><main>' + body + '</main></html>'
    write_new(output / "index.html", document.encode())
    write_new(output / "proposal.json", (encoded(p) + '\n').encode())
    write_new(output / "evaluation.json", (encoded(gate) + '\n').encode())
    write_new(output / "README.md", (f"# {p['title']}\n\n{status}\n\nOpen index.html for the complete review.\n\nRevision: {revision}\nPacket SHA-256: {gate['packet_hash']}\n\nThis export is a review snapshot, not a production release or a live approval status.\n").encode())
    files = {f.relative_to(output).as_posix(): digest(f.read_bytes()) for f in sorted(output.rglob("*")) if f.is_file()}
    write_new(output / "manifest.json", (encoded({"project": project, "revision": revision, "files": files, "attachments": attachments}) + '\n').encode())
    return {"directory": str(output), "html": str(output / "index.html"), "revision": revision, "engineering_ready": gate["engineering_ready"], "human_review_required": True}
