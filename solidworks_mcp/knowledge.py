"""
Design knowledge base
---------------------
Markdown notes in ../knowledge (one topic per file, "## " sections). Each file starts with
a small front matter block:

    ---
    title: Gears
    tags: gear, 기어, spur, 스퍼, bevel, 베벨
    summary: one line
    ---

knowledge_search returns short snippets (cheap); knowledge_get returns one section.
Notes are written in English (fewer tokens); tags carry Korean keywords for search.
"""

import re
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge"
_TOKEN = re.compile(r"[0-9a-z가-힣]+(?:[./][0-9a-z]+)*")


def _slug(text):
    return re.sub(r"[^0-9a-z가-힣]+", "-", text.lower()).strip("-")


# Korean keywords -> English terms used in the notes (prefix match, so "기어의" also hits "기어")
KO_EN = {
    "스파이럴": "spiral", "나선": "spiral hand", "베벨": "bevel", "마이터": "miter", "기어": "gear", "치차": "gear",
    "스퍼": "spur", "헬리컬": "helical", "웜": "worm", "유성": "planetary", "하모닉": "strain wave harmonic",
    "사이클로": "cycloidal", "모듈": "module", "압력각": "pressure angle", "잇수": "teeth", "백래시": "backlash",
    "인볼류트": "involute", "랙": "rack", "방향": "hand direction", "왼": "left hand", "오른": "right hand",
    "물림": "mesh", "맞물": "mesh", "간섭": "interference", "베어링": "bearing", "수명": "life", "예압": "preload",
    "숄더": "shoulder", "볼트": "bolt screw", "나사": "screw thread", "탭": "tap thread", "구멍": "hole",
    "관통": "clearance hole", "카운터보어": "counterbore", "자리파기": "counterbore", "토크": "torque",
    "인서트": "insert", "다웰": "dowel pin", "핀": "pin", "너트": "nut", "와셔": "washer", "체결": "fastener",
    "공차": "tolerance", "끼워맞춤": "fit", "억지": "interference press fit", "압입": "press fit",
    "헐거운": "clearance fit", "일반공차": "iso 2768", "거칠기": "roughness", "축": "shaft", "샤프트": "shaft",
    "키홈": "keyway", "키": "key", "스냅링": "retaining ring", "멈춤링": "retaining ring", "처짐": "deflection",
    "비틀림": "torsion", "굽힘": "bending", "재료": "material", "재질": "material", "소재": "material",
    "알루미늄": "aluminium aluminum", "스테인리스": "stainless sus304", "강": "steel", "탄성": "modulus",
    "밀도": "density", "항복": "yield", "나일론": "pa nylon", "아세탈": "pom", "가공": "machining milling",
    "판금": "sheet metal bend", "사출": "injection moulding", "프린팅": "printing fdm", "프린트": "printing fdm",
    "출력": "printing", "오버행": "overhang", "두께": "wall thickness", "필렛": "fillet", "모따기": "chamfer",
    "구배": "draft", "근거": "basis", "기본값": "default neutral", "대칭": "symmetry mirror", "안전율": "safety factor",
    "표준수": "preferred numbers renard", "토큰": "token", "절약": "token budget", "가이드": "guide",
    "워크플로": "workflow loop", "반복": "iteration", "품질": "quality gate", "보고": "report",
    "로프트": "loft", "패턴": "pattern", "구성": "configuration", "메이트": "mate", "어셈블리": "assembly",
    "스케치": "sketch", "돌출": "extrude", "회전": "revolve", "질량": "mass", "내보내기": "export",
    "렌더": "render image", "이미지": "image render", "평면": "plane", "한국어": "localized korean",
}
_KO_KEYS = sorted(KO_EN, key=len, reverse=True)


def _tokens(text):
    found = _TOKEN.findall(text.lower())
    extra = []
    for tok in found:
        if any("가" <= ch <= "힣" for ch in tok):
            for key in _KO_KEYS:
                if tok.startswith(key):
                    extra.extend(KO_EN[key].split())
                    break
    return found + extra


class KnowledgeBase:
    def __init__(self, root=KB_DIR):
        self.root = Path(root)
        self.topics = {}      # stem -> {"title", "tags", "summary", "sections": [ids]}
        self.sections = {}    # id -> {"topic", "heading", "text", "tags"}
        self.load()

    def load(self):
        self.topics.clear()
        self.sections.clear()
        if not self.root.is_dir():
            return
        for path in sorted(self.root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            meta, body = {}, text
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
            if match:
                body = text[match.end():]
                for line in match.group(1).splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        meta[key.strip().lower()] = value.strip()
            stem = path.stem
            title = meta.get("title", stem)
            tags = [t.strip().lower() for t in meta.get("tags", "").split(",") if t.strip()]
            topic = {"title": title, "tags": tags, "summary": meta.get("summary", ""), "sections": []}
            parts = re.split(r"(?m)^## +", body)
            chunks = [("Overview", parts[0])] + [(p.split("\n", 1)[0].strip(), p.split("\n", 1)[1] if "\n" in p else "")
                                                 for p in parts[1:]]
            for heading, chunk in chunks:
                chunk = chunk.strip()
                if not chunk or chunk.startswith("# ") and len(chunk.splitlines()) == 1:
                    continue
                sid = f"{stem}#{_slug(heading) or 'overview'}"
                self.sections[sid] = {"topic": title, "heading": heading, "text": chunk, "tags": tags}
                topic["sections"].append(sid)
            self.topics[stem] = topic

    def index(self):
        return {stem: {"title": t["title"], "summary": t["summary"],
                       "sections": [s.split("#", 1)[1] for s in t["sections"]]}
                for stem, t in self.topics.items()}

    def search(self, query, limit=5):
        terms = list(dict.fromkeys(_tokens(query)))
        if not terms:
            return []
        scored = []
        for sid, sec in self.sections.items():
            body = sec["text"].lower()
            heading = sec["heading"].lower()
            topic = sec["topic"].lower()
            tags = " ".join(sec["tags"])
            score = 0.0
            for term in terms:
                score += min(body.count(term), 6)
                score += 4 * (term in heading) + 2 * (term in topic) + 3 * (term in tags)
            if score:
                scored.append((score, sid))
        scored.sort(key=lambda s: -s[0])
        results = []
        for score, sid in scored[:max(1, int(limit))]:
            sec = self.sections[sid]
            flat = " ".join(sec["text"].split())
            pos = min([i for i in (flat.lower().find(t) for t in terms) if i >= 0] or [0])
            start = max(0, pos - 60)
            snippet = ("…" if start else "") + flat[start:start + 220] + ("…" if start + 220 < len(flat) else "")
            results.append({"id": sid, "topic": sec["topic"], "section": sec["heading"], "snippet": snippet})
        return results

    def get(self, ref, max_chars=8000):
        ref = (ref or "").strip()
        if ref.lower() in ("", "index", "topics", "list"):
            return {"index": self.index()}
        if ref in self.sections:
            sec = self.sections[ref]
            text = sec["text"]
            return {"id": ref, "topic": sec["topic"], "section": sec["heading"],
                    "text": text[:max_chars] + ("\n…(truncated)" if len(text) > max_chars else "")}
        stem = ref.split("#", 1)[0]
        if stem in self.topics:
            if "#" in ref:
                return {"error": f"no section '{ref}'", "sections": self.topics[stem]["sections"]}
            parts = [f"## {self.sections[s]['heading']}\n{self.sections[s]['text']}" for s in self.topics[stem]["sections"]]
            text = "\n\n".join(parts)
            return {"id": stem, "topic": self.topics[stem]["title"],
                    "text": text[:max_chars] + ("\n…(truncated, ask for one section)" if len(text) > max_chars else "")}
        import difflib
        close = difflib.get_close_matches(ref, list(self.topics) + list(self.sections), n=3, cutoff=0.5)
        return {"error": f"'{ref}' not found", "suggestions": close or [r["id"] for r in self.search(ref, 3)]}


_KB = None


def kb():
    global _KB
    if _KB is None:
        _KB = KnowledgeBase()
    return _KB
