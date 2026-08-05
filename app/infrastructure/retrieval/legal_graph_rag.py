"""GraphRAG: hybrid PG seeds → Neo4j expand → hydrate texts from Postgres."""

from datetime import date

from app.core.logging import logger
from app.core.settings import get_settings
from app.domain.entities.search import RetrievedChunk
from app.domain.ports.repositories import LegalChunkRepository
from app.domain.ports.services import GraphRepository, LegalVectorSearch
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query

_STATUS_RANK = {0: 0.40, 1: 1.00, 2: 0.00, 3: 0.60, 4: 0.50}


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
        as_of_date: str | None = None,
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

        # Self-correct: if the combined query still returns nothing, try narrower
        # single-source formulations (LLM-free) before giving up for this clause.
        if not seeds:
            variants = []
            if contract_type:
                variants.append(contract_type.strip())
            if title:
                variants.append(title.strip())
            if summary:
                variants.append(summary.strip())
            for variant in dict.fromkeys(v for v in variants if v):
                hits = self._search.search(variant, k=k_seed, min_score=0.0)
                if hits:
                    logger.info(
                        "LegalGraphRag: seed recovery via narrow query %r hits=%s",
                        variant[:60], len(hits),
                    )
                    seeds = hits
                    break
        if not seeds:
            logger.warning("LegalGraphRag: still 0 seeds after narrow query fallbacks query=%r", query[:80])
        for s in seeds:
            s.metadata["role"] = "seed"

        by_ref: dict[str, RetrievedChunk] = {
            s.metadata["chunk_ref"]: s for s in seeds if s.metadata.get("chunk_ref")
        }
        repealed: set[str] = set()
        superseding_added = 0

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
                        "eff_from": meta.get("eff_from"),
                        "eff_to": meta.get("eff_to"),
                        "status_flag": meta.get("status_flag"),
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

            # Flag seeds whose source doc has been repealed/superseded.
            if repealed and len(by_ref) > 2:
                for ref, chunk in list(by_ref.items()):
                    if chunk.metadata.get("doc_id") in repealed and chunk.metadata.get("role") == "seed":
                        chunk.metadata["note"] = "source_doc_may_be_repealed"

            # Fetch the TEXT of replacing docs so the LLM can cite current law
            # instead of blanking when a seed is flagged expired.
            superseding_added = 0
            if repealed:
                for d_id in repealed:
                    superseding_hits = self._search.search_in_docs(query, [d_id], k=2)
                    for h in superseding_hits:
                        ref = h.metadata.get("chunk_ref")
                        if not ref or ref in by_ref:
                            continue
                        h.metadata["role"] = "superseding"
                        h.metadata["note"] = f"replaces {d_id}"
                        by_ref[ref] = h
                        superseding_added += 1

        ordered = self._order_for_prompt(list(by_ref.values()), as_of=as_of_date)
        result = ordered[:max_total]
        logger.info(
            "LegalGraphRag query=%r seeds=%s repealed_seeds=%s superseding=%s total=%s",
            query[:80],
            sum(1 for c in result if c.metadata.get("role") == "seed"),
            len(repealed) if repealed else 0,
            superseding_added,
            len(result),
        )
        return result

    @staticmethod
    def format_context(chunks: list[RetrievedChunk], max_chars: int = 7000) -> str:
        _SF_MAP = {0: "chưa xác định", 1: "còn hiệu lực", 2: "hết hiệu lực", 3: "sắp có hiệu lực", 4: "hết hiệu lực một phần"}
        sections = {
            "seed": [],
            "superseding": [],
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
            sf = c.metadata.get("status_flag")
            status_text = _SF_MAP.get(sf, "") if sf is not None else ""
            header = f"[{label} | {ref} | {role}]"
            if status_text:
                header += f" [{status_text}]"
            if note:
                header += f" ({note})"
            sections[role].append(f"{header}\n{c.content}")

        blocks = []
        if sections["seed"]:
            blocks.append("### Điều luật seed (truy hồi trực tiếp)\n" + "\n\n".join(sections["seed"]))
        if sections["superseding"]:
            blocks.append(
                "### Văn bản thay thế / kế thừa (thay cho seed đã hết hiệu lực)\n"
                + "\n\n".join(sections["superseding"])
            )
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
    def _validity_key(chunk: RetrievedChunk, as_of: str | None = None) -> tuple[int, float]:
        sf = chunk.metadata.get("status_flag")
        if sf is None:
            return (2, 0.40)
        try:
            sf = int(sf)
        except (TypeError, ValueError):
            return (2, 0.40)
        ref_date = as_of or str(date.today())
        eff_from = chunk.metadata.get("eff_from")
        eff_to = chunk.metadata.get("eff_to")

        if sf == 2 or sf == 4:
            sf_effective = sf == 4
        else:
            sf_effective = sf != 2
            if eff_to and isinstance(eff_to, str) and eff_to[:10] < ref_date[:10]:
                sf_effective = False
            if eff_from and isinstance(eff_from, str) and eff_from[:10] > ref_date[:10]:
                sf_effective = False

        rank = _STATUS_RANK.get(sf, 0.40)
        if not sf_effective:
            rank = 0.0
        priority = 0 if sf_effective else 99
        return (priority, -rank)

    @staticmethod
    def _order_for_prompt(chunks: list[RetrievedChunk], as_of: str | None = None) -> list[RetrievedChunk]:
        rank = {"seed": 0, "sibling": 1, "ancestor": 2, "related": 3}
        return sorted(
            chunks,
            key=lambda c: (
                LegalGraphRag._validity_key(c, as_of)[0],
                rank.get(c.metadata.get("role") or "seed", 9),
                -(c.score or 0),
            ),
        )
