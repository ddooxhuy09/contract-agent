"""GraphRAG: hybrid PG seeds → Neo4j expand → hydrate texts from Postgres."""

from app.core.logging import logger
from app.core.settings import get_settings
from app.domain.entities.search import RetrievedChunk
from app.domain.ports.repositories import LegalChunkRepository
from app.domain.ports.services import GraphRepository, LegalVectorSearch
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query


class LegalGraphRag:
    def __init__(
        self,
        legal_search: LegalVectorSearch,
        legal_chunks: LegalChunkRepository,
        graph: GraphRepository | None,
    ):
        self._search = legal_search
        self._chunks = legal_chunks
        self._graph = graph

    def retrieve_for_clause(
        self,
        title: str | None,
        summary: str | None,
        *,
        contract_type: str | None = None,
        k_seed: int = 4,
        max_total: int = 10,
    ) -> list[RetrievedChunk]:
        settings = get_settings()
        query = rewrite_legal_query(title, summary, contract_type)
        # Do NOT pass contract_type as SQL doc_type_hint — it filters legal rows by
        # title/doc_type ILIKE and often zeros the corpus (e.g. "HĐLĐ" vs "Nghị định").
        # contract_type is already folded into the query text by rewrite_legal_query.
        seeds = self._search.search(
            query,
            k=k_seed,
            min_score=settings.similarity_threshold,
        )
        if not seeds:
            logger.warning(
                "LegalGraphRag: 0 seeds above threshold=%.2f; retrying without score floor query=%r",
                settings.similarity_threshold,
                query[:80],
            )
            seeds = self._search.search(query, k=k_seed, min_score=0.0)
        for s in seeds:
            s.metadata["role"] = "seed"

        by_ref: dict[str, RetrievedChunk] = {
            s.metadata["chunk_ref"]: s for s in seeds if s.metadata.get("chunk_ref")
        }

        if self._graph and by_ref:
            expansion = self._graph.expand(list(by_ref.keys()))
            sibling_refs = expansion.get("sibling_paths") or []
            ancestor_refs = expansion.get("ancestor_paths") or []
            parent_clause_refs = expansion.get("parent_clause_paths") or []
            related_docs = expansion.get("related_docs") or []
            repealed = set(expansion.get("repealed_by_docs") or [])

            hydrate_refs = list(
                dict.fromkeys([*sibling_refs, *ancestor_refs, *parent_clause_refs])
            )
            texts = self._chunks.get_texts_by_refs(hydrate_refs)
            meta_rows = self._chunks.get_meta_by_refs(hydrate_refs)

            for ref, text in texts.items():
                if ref in by_ref:
                    continue
                role = "sibling" if ref in sibling_refs else "ancestor"
                if ref in parent_clause_refs:
                    role = "sibling"
                meta = meta_rows.get(ref, {})
                by_ref[ref] = RetrievedChunk(
                    content=text,
                    score=None,
                    metadata={
                        "chunk_ref": ref,
                        "doc_id": meta.get("doc_id"),
                        "chunk_type": meta.get("chunk_type", "body"),
                        "doc_number": meta.get("doc_number"),
                        "title": meta.get("title"),
                        "role": role,
                    },
                )

            if related_docs:
                related_hits = self._search.search_in_docs(query, related_docs, k=2)
                for h in related_hits:
                    ref = h.metadata.get("chunk_ref")
                    if not ref or ref in by_ref:
                        continue
                    h.metadata["role"] = "related"
                    if h.metadata.get("doc_id") in repealed:
                        h.metadata["note"] = "source_doc_may_be_repealed"
                    by_ref[ref] = h

            # Drop seeds from docs that are clearly repealed if we have alternatives
            if repealed and len(by_ref) > 2:
                for ref, chunk in list(by_ref.items()):
                    if chunk.metadata.get("doc_id") in repealed and chunk.metadata.get("role") == "seed":
                        chunk.metadata["note"] = "source_doc_may_be_repealed"

        ordered = self._order_for_prompt(list(by_ref.values()))
        result = ordered[:max_total]
        logger.info(
            "LegalGraphRag query=%r seeds=%s total=%s",
            query[:80],
            sum(1 for c in result if c.metadata.get("role") == "seed"),
            len(result),
        )
        return result

    @staticmethod
    def format_context(chunks: list[RetrievedChunk], max_chars: int = 7000) -> str:
        sections = {
            "seed": [],
            "sibling": [],
            "ancestor": [],
            "related": [],
        }
        for c in chunks:
            role = c.metadata.get("role") or "seed"
            if role not in sections:
                role = "seed"
            label = c.metadata.get("doc_number") or c.metadata.get("title") or "Nguồn"
            ref = c.metadata.get("chunk_ref") or ""
            note = c.metadata.get("note")
            header = f"[{label} | {ref} | {role}]"
            if note:
                header += f" ({note})"
            sections[role].append(f"{header}\n{c.content}")

        blocks = []
        if sections["seed"]:
            blocks.append("### Điều luật seed (truy hồi trực tiếp)\n" + "\n\n".join(sections["seed"]))
        if sections["sibling"] or sections["ancestor"]:
            blocks.append(
                "### Cùng khoản / ngữ cảnh cây (hydrate GraphRAG)\n"
                + "\n\n".join(sections["sibling"] + sections["ancestor"])
            )
        if sections["related"]:
            blocks.append(
                "### Văn bản liên quan (BASED_ON/CITES/AMENDS…)\n"
                + "\n\n".join(sections["related"])
            )
        text = "\n\n".join(blocks)
        return text[:max_chars]

    @staticmethod
    def _order_for_prompt(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        rank = {"seed": 0, "sibling": 1, "ancestor": 2, "related": 3}
        return sorted(
            chunks,
            key=lambda c: (
                rank.get(c.metadata.get("role") or "seed", 9),
                -(c.score or 0),
            ),
        )
