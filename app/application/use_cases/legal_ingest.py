"""Legal ingest — accepts in-memory artifacts (from legal_corpus assemble or fixtures)."""

from datetime import date, datetime
from typing import Any

from app.core.logging import logger
from app.domain.entities.legal import LegalChunk, LegalDocRelation, LegalDocument
from app.domain.ports.repositories import LegalChunkRepository, LegalDocumentRepository
from app.domain.ports.services import Embedder, GraphRepository


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class IngestLegalDocument:
    """Upsert thuoc_tinh + chunks (+ optional relations) into PG and Neo4j."""

    def __init__(
        self,
        legal_docs: LegalDocumentRepository,
        legal_chunks: LegalChunkRepository,
        embedder: Embedder,
        graph: GraphRepository,
    ):
        self._docs = legal_docs
        self._chunks = legal_chunks
        self._embedder = embedder
        self._graph = graph

    def execute(
        self,
        thuoc_tinh: dict[str, Any],
        chunks: list[dict[str, Any]],
        relations: list[dict[str, str]] | None = None,
        graph_nodes: list[dict[str, Any]] | None = None,
        stub_docs: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        doc_id = str(thuoc_tinh["doc_id"])
        doc = LegalDocument(
            doc_id=doc_id,
            doc_num=str(thuoc_tinh.get("doc_num") or ""),
            doc_num_norm=thuoc_tinh.get("doc_num_norm"),
            title=str(thuoc_tinh.get("title") or ""),
            doc_type=str(thuoc_tinh.get("doc_type") or "Unknown"),
            majors=list(thuoc_tinh.get("majors") or []),
            fields=list(thuoc_tinh.get("fields") or []),
            issue_date=_parse_date(thuoc_tinh.get("issue_date")),
            eff_from=_parse_date(thuoc_tinh.get("eff_from")),
            eff_to=_parse_date(thuoc_tinh.get("eff_to")),
            eff_status=thuoc_tinh.get("eff_status"),
            eff_status_code=thuoc_tinh.get("eff_status_code"),
            status_flag=int(thuoc_tinh.get("status_flag") or 1),
            agency=thuoc_tinh.get("agency"),
            signers=list(thuoc_tinh.get("signers") or []),
            source_url=thuoc_tinh.get("source_url"),
            full_text=thuoc_tinh.get("full_text"),
        )
        self._docs.upsert(doc)

        texts = [c["chunk_text"] for c in chunks]
        vectors = self._embedder.embed_documents(texts) if texts else []
        entities = [
            LegalChunk(
                chunk_ref=c["chunk_ref"],
                doc_id=doc_id,
                chunk_text=c["chunk_text"],
                chunk_type=c.get("chunk_type", "body"),
                embedding=vectors[i] if i < len(vectors) else None,
                is_effective=bool(c.get("is_effective", True)),
            )
            for i, c in enumerate(chunks)
        ]
        self._chunks.upsert_many(entities)

        rel_entities = [
            LegalDocRelation(
                from_doc_id=r["from_doc_id"],
                to_doc_id=r["to_doc_id"],
                relation_type=r["relation_type"],
            )
            for r in (relations or [])
        ]
        stubs = stub_docs or {}
        if rel_entities:
            for rel in rel_entities:
                for other_id in (rel.from_doc_id, rel.to_doc_id):
                    if other_id == doc_id:
                        continue
                    if self._docs.get(other_id) is not None:
                        continue
                    meta = stubs.get(other_id) or {}
                    self._docs.upsert(
                        LegalDocument(
                            doc_id=other_id,
                            doc_num=str(meta.get("doc_num") or other_id),
                            title=str(meta.get("title") or f"Stub {other_id}"),
                            doc_type=str(meta.get("doc_type") or "Unknown"),
                            issue_date=_parse_date(meta.get("issue_date")),
                            eff_from=_parse_date(meta.get("eff_from")),
                            eff_to=_parse_date(meta.get("eff_to")),
                            status_flag=int(meta.get("status_flag") or 0),
                        )
                    )
            self._docs.upsert_relations(rel_entities)

        nodes = graph_nodes or [
            {
                "path": c["chunk_ref"],
                "level": "Point" if c.get("chunk_type", "body") == "body" else "Meta",
                "label": c["chunk_ref"],
                "parent_path": None,
            }
            for c in chunks
        ]
        self._graph.upsert_document_tree(
            doc_id=doc_id,
            doc_num=doc.doc_num,
            doc_type=doc.doc_type,
            nodes=nodes,
            chunks=[{"chunk_ref": c.chunk_ref, "chunk_type": c.chunk_type} for c in entities],
        )
        if rel_entities:
            self._graph.upsert_doc_relations(
                [
                    {
                        "from_doc_id": r.from_doc_id,
                        "to_doc_id": r.to_doc_id,
                        "relation_type": r.relation_type,
                    }
                    for r in rel_entities
                ]
            )

        logger.info("Ingested legal doc_id=%s chunks=%s", doc_id, len(entities))
        return {"doc_id": doc_id, "chunk_count": len(entities), "relation_count": len(rel_entities)}
