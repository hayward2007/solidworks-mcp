"""Small hand-authored retrieval relevance smoke set, not an LLM/product-quality benchmark."""
import json
import tempfile
from solidworks_mcp.design.store import Store
from solidworks_mcp.design.retrieval import Retriever

CASES = [
    ("카메라 시야 역경사", "sensor-enclosure.md"),
    ("외형 실루엣 파팅 정비", "industrial-design.md"),
    ("공차 가공 조립", "manufacturing-detail.md"),
    ("역설계 실측 좌표", "reverse-engineering.md"),
    ("approval review iteration", "design-review.md"),
    ("source standard applicability ISO", "standards-registry.md"),
    ("evidence provenance uncertainty", "design-evidence.md"),
    ("quality before compression", "product-design-policy.md"),
    ("설계 예제 처짐 브래킷", "design-examples.md"),
]


def evaluate():
    with tempfile.TemporaryDirectory() as tmp, Store(tmp) as store:
        retriever = Retriever(store)
        index = retriever.index()
        results = []
        for query, expected in CASES:
            hits = retriever.search(query, 8)
            rank = next((i + 1 for i, row in enumerate(hits) if row["path"] == expected), None)
            results.append({"query": query, "expected_document": expected, "rank": rank, "hit_at_8": rank is not None})
        return {"index": index, "cases": results, "document_recall_at_8": sum(x["hit_at_8"] for x in results) / len(results),
                "scope": "Nine hand-authored routing checks only; no claim of semantic search superiority, generation quality or measured token savings."}


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["document_recall_at_8"] == 1 else 1)
