"""Ingest a tiny in-memory legal sample (no dump). Usage: python -m scripts.ingest_legal_sample"""

from app.application.use_cases.legal_ingest import IngestLegalDocument
from app.infrastructure.container import build_container
from app.infrastructure.db.schema_loader import apply_postgres_schema


def main() -> None:
    apply_postgres_schema()
    c = build_container()
    try:
        c.graph.ensure_schema()
    except Exception:
        pass
    result = IngestLegalDocument(c.legal_docs, c.legal_chunks, c.embedder, c.graph).execute(
        thuoc_tinh={
            "doc_id": "sample-168",
            "doc_num": "168/2024/NĐ-CP",
            "title": "Nghị định mẫu (fixture)",
            "doc_type": "Nghị định",
            "status_flag": 1,
        },
        chunks=[
            {
                "chunk_ref": "C1.D1.K1.a",
                "chunk_type": "body",
                "chunk_text": (
                    "Điều 1. Phạm vi điều chỉnh\n"
                    "1. Nghị định này quy định xử phạt.\n"
                    "a) Hành vi vi phạm trật tự an toàn giao thông."
                ),
            }
        ],
        graph_nodes=[
            {"path": "C1", "level": "Chapter", "label": "Chương I", "parent_path": None},
            {"path": "C1.D1", "level": "Article", "label": "Điều 1", "parent_path": "C1"},
            {"path": "C1.D1.K1", "level": "Clause", "label": "Khoản 1", "parent_path": "C1.D1"},
            {"path": "C1.D1.K1.a", "level": "Point", "label": "Điểm a", "parent_path": "C1.D1.K1"},
        ],
    )
    print(result)


if __name__ == "__main__":
    main()
