"""Hierarchy effectiveness: LegalNode fields, ingest inherit, cascade rules (doc'd)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.application.use_cases.legal_ingest import IngestLegalDocument
from app.domain.entities.legal import LegalChunk, LegalNode


def test_legal_node_effectiveness_fields():
    n = LegalNode(
        doc_id="d1",
        level="Article",
        path="d1.D1",
        eff_from=date(2018, 1, 1),
        eff_to=None,
        eff_flag="Còn hiệu lực",
        status_flag=1,
    )
    assert n.eff_from == date(2018, 1, 1)
    assert n.status_flag == 1
    assert not hasattr(n, "eff_date")


def test_ingest_inherits_doc_effectiveness_onto_nodes():
    docs = MagicMock()
    docs.get.return_value = None
    chunks_repo = MagicMock()
    graph = MagicMock()
    embedder = MagicMock()
    embedder.embed_documents.return_value = [[0.1] * 8]

    uc = IngestLegalDocument(docs, chunks_repo, embedder, graph)
    uc.execute(
        thuoc_tinh={
            "doc_id": "d1",
            "doc_num": "1",
            "title": "T",
            "doc_type": "Luật",
            "eff_from": "2018-01-01",
            "eff_to": "2030-01-01",
            "eff_flag": "Còn hiệu lực",
            "status_flag": 1,
        },
        chunks=[
            {
                "path": "d1.D1.K1",
                "chunk_text": "hello",
                "chunk_type": "body",
            }
        ],
        legal_nodes=[
            {
                "doc_id": "d1",
                "level": "Article",
                "path": "d1.D1",
                "label": "Điều 1",
            }
        ],
        relations=[],
        graph_nodes=[],
    )

    nodes = chunks_repo.upsert_nodes.call_args[0][0]
    assert len(nodes) == 1
    assert isinstance(nodes[0], LegalNode)
    assert nodes[0].eff_from == date(2018, 1, 1)
    assert nodes[0].eff_to == date(2030, 1, 1)
    assert nodes[0].status_flag == 1
    assert nodes[0].eff_flag == "Còn hiệu lực"

    entities = chunks_repo.upsert_many.call_args[0][0]
    assert isinstance(entities[0], LegalChunk)
    assert entities[0].is_effective is True


def test_ingest_chunk_ineffective_when_doc_expired():
    docs = MagicMock()
    docs.get.return_value = None
    chunks_repo = MagicMock()
    graph = MagicMock()
    embedder = MagicMock()
    embedder.embed_documents.return_value = [[0.1] * 8]

    uc = IngestLegalDocument(docs, chunks_repo, embedder, graph)
    uc.execute(
        thuoc_tinh={
            "doc_id": "d2",
            "doc_num": "2",
            "title": "T",
            "doc_type": "Luật",
            "status_flag": 2,
            "eff_flag": "Hết hiệu lực toàn bộ",
        },
        chunks=[{"path": "d2.D1", "chunk_text": "x", "chunk_type": "body"}],
        legal_nodes=[],
        relations=[],
        graph_nodes=[],
    )
    entities = chunks_repo.upsert_many.call_args[0][0]
    assert entities[0].is_effective is False


def test_cascade_rules_documented_in_schema_sql():
    """Smoke: schema defines cascade + embedding sync functions."""
    from pathlib import Path

    sql = Path("schema.sql").read_text(encoding="utf-8")
    assert "trg_hierarchy_cascade_expire" in sql
    assert "trg_sync_embedding_effective" in sql
    assert "refresh_hierarchy_status_flags" in sql
    art = sql.split("CREATE TABLE IF NOT EXISTS legal_articles")[1].split(
        "CREATE TABLE IF NOT EXISTS legal_clauses"
    )[0]
    assert "eff_from" in art
    assert "eff_date" not in art
    assert "status_flag" in art
