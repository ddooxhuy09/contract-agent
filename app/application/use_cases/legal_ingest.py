"""Legal ingest — accepts in-memory artifacts (from legal_corpus assemble or fixtures)."""

from datetime import date, datetime
from typing import Any

from app.core.logging import logger
from app.domain.entities.legal import (
    LegalChunk,
    LegalChunkRelation,
    LegalDocRelation,
    LegalDocument,
    LegalNode,
)
from app.domain.ports.repositories import LegalChunkRepository, LegalDocumentRepository
from app.domain.ports.services import Embedder, GraphRepository
from app.infrastructure.legal_corpus.muc_luc_paths import article_root_ltree, chunk_ref_to_ltree


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
    """Upsert thuoc_tinh + nodes + chunks (+ optional relations) into PG and Neo4j."""

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
        legal_nodes: list[dict[str, Any]] | None = None,
        path_relations: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        doc_id = str(thuoc_tinh["doc_id"])
        doc = LegalDocument(
            doc_id=doc_id,
            doc_num=str(thuoc_tinh.get("doc_num") or ""),
            title=str(thuoc_tinh.get("title") or ""),
            doc_type=str(thuoc_tinh.get("doc_type") or "Unknown"),
            majors=list(thuoc_tinh.get("majors") or []),
            fields=list(thuoc_tinh.get("fields") or []),
            issue_date=_parse_date(thuoc_tinh.get("issue_date")),
            eff_from=_parse_date(thuoc_tinh.get("eff_from")),
            eff_to=_parse_date(thuoc_tinh.get("eff_to")),
            eff_flag=thuoc_tinh.get("eff_flag"),
            status_flag=int(thuoc_tinh.get("status_flag") or 1),
            agency=thuoc_tinh.get("agency"),
            signer_name=thuoc_tinh.get("signer_name"),
            signer_title=thuoc_tinh.get("signer_title"),
            source_url=thuoc_tinh.get("source_url"),
            full_text=thuoc_tinh.get("full_text"),
        )
        self._docs.upsert(doc)

        node_rows = legal_nodes or []
        if node_rows:
            doc_eff_from = _parse_date(thuoc_tinh.get("eff_from"))
            doc_eff_to = _parse_date(thuoc_tinh.get("eff_to"))
            doc_eff_flag = thuoc_tinh.get("eff_flag")
            doc_status = int(thuoc_tinh.get("status_flag") or 1)
            self._chunks.upsert_nodes(
                [
                    LegalNode(
                        doc_id=str(n.get("doc_id") or doc_id),
                        level=str(n.get("level") or "Other"),
                        path=str(n["path"]),
                        label=n.get("label"),
                        parent_path=n.get("parent_path"),
                        sort_order=n.get("sort_order"),
                        eff_from=_parse_date(n.get("eff_from")) or doc_eff_from,
                        eff_to=_parse_date(n.get("eff_to")) or doc_eff_to,
                        eff_flag=n.get("eff_flag") or doc_eff_flag,
                        status_flag=int(
                            n["status_flag"]
                            if n.get("status_flag") is not None
                            else doc_status
                        ),
                        muc_luc_id=n.get("muc_luc_id"),
                    )
                    for n in node_rows
                    if n.get("path")
                ]
            )

        texts = [c["chunk_text"] for c in chunks]
        vectors = self._embedder.embed_documents(texts) if texts else []
        entities = []
        doc_status = int(thuoc_tinh.get("status_flag") or 1)
        default_eff = doc_status in (1, 5)
        for i, c in enumerate(chunks):
            path = c.get("path") or (
                chunk_ref_to_ltree(c["chunk_ref"]) if c.get("chunk_ref") else None
            )
            if not path:
                continue
            entities.append(
                LegalChunk(
                    doc_id=doc_id,
                    chunk_text=c["chunk_text"],
                    path=path,
                    source_element_id=c.get("source_element_id"),
                    chunk_type=c.get("chunk_type", "body"),
                    embedding=vectors[i] if i < len(vectors) else None,
                    is_effective=bool(c.get("is_effective", default_eff)),
                    root_path=c.get("root_path") or article_root_ltree(path),
                )
            )
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

        path_rel_entities = [
            LegalChunkRelation(
                from_path=r["source_path"],
                to_path=r["target_path"],
                relation_type=r.get("ref_type") or "dan_chieu",
            )
            for r in (path_relations or [])
            if r.get("source_path") and r.get("target_path")
        ]
        if path_rel_entities:
            self._chunks.upsert_relations(path_rel_entities)

        nodes = graph_nodes or [
            {
                "path": c.path,
                "level": "Point" if c.chunk_type == "body" else "Meta",
                "label": c.path,
                "parent_path": None,
            }
            for c in entities
        ]
        self._graph.upsert_document_tree(
            doc_id=doc_id,
            doc_num=doc.doc_num,
            doc_type=doc.doc_type,
            nodes=nodes,
            chunks=[{"path": c.path, "chunk_type": c.chunk_type} for c in entities],
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

        logger.info(
            "Ingested legal doc_id=%s chunks=%s nodes=%s path_rels=%s",
            doc_id,
            len(entities),
            len(node_rows),
            len(path_rel_entities),
        )
        return {
            "doc_id": doc_id,
            "chunk_count": len(entities),
            "node_count": len(node_rows),
            "relation_count": len(rel_entities),
            "path_relation_count": len(path_rel_entities),
        }
