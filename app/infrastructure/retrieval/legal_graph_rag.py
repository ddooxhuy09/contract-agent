"""GraphRAG: hybrid PG seeds → expand (Neo4j and/or PG ltree) → hydrate by path."""

from datetime import date

from app.agents.labor_code_resolver import _parse_as_of
from app.core.logging import logger
from app.core.settings import get_settings
from app.domain.entities.search import RetrievedChunk
from app.domain.ports.repositories import LegalChunkRepository
from app.domain.ports.services import GraphRepository, LegalVectorSearch
from app.infrastructure.legal_corpus.muc_luc_paths import chunk_ref_to_ltree
from app.infrastructure.retrieval.query_rewrite import rewrite_legal_query
from app.infrastructure.retrieval.normative_rank import normative_rank
from app.infrastructure.retrieval.scope_match import (
    contract_context,
    filter_sector_mismatches,
)

# 0/? 1 còn 2 hết/ngưng 3 chưa HL 4 hết 1 phần 5 còn 1 phần
_STATUS_RANK = {0: 0.40, 1: 1.00, 2: 0.00, 3: 0.55, 4: 0.50, 5: 0.85}

_EMPTY_EXPAND = {
    "sibling_paths": [],
    "ancestor_paths": [],
    "parent_clause_paths": [],
    "related_docs": [],
    "repealed_by_docs": [],
}


def _chunk_key(meta: dict) -> str | None:
    return meta.get("path")


def _to_ltree_key(key: str | None) -> str | None:
    if not key:
        return None
    if ":" in key:
        return chunk_ref_to_ltree(key) or key
    return key


def _normalize_expand_to_paths(expansion: dict) -> dict:
    """Normalize expand lists to ltree path keys."""
    out = {}
    for field in ("sibling_paths", "ancestor_paths", "parent_clause_paths"):
        out[field] = [
            p for p in (_to_ltree_key(k) for k in (expansion.get(field) or [])) if p
        ]
    out["related_docs"] = list(expansion.get("related_docs") or [])
    out["repealed_by_docs"] = list(expansion.get("repealed_by_docs") or [])
    return out


def _merge_expand(primary: dict, secondary: dict) -> dict:
    """Union list fields; primary wins order, secondary fills gaps."""
    out = {}
    for key in _EMPTY_EXPAND:
        a = list(primary.get(key) or [])
        b = list(secondary.get(key) or [])
        out[key] = list(dict.fromkeys([*a, *b]))
    return out


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

    def _expand(self, seed_keys: list[str]) -> dict:
        backend = (get_settings().legal_expand_backend or "neo4j").strip().lower()
        path_keys = [k for k in (_to_ltree_key(k) for k in seed_keys) if k]

        neo: dict = dict(_EMPTY_EXPAND)
        pg: dict = dict(_EMPTY_EXPAND)
        if backend in ("neo4j", "both") and self._graph is not None and path_keys:
            try:
                neo = _normalize_expand_to_paths(self._graph.expand(path_keys) or neo)
            except Exception as e:
                logger.warning("Neo4j expand failed: %s", e)
        if backend in ("postgres", "both"):
            try:
                pg = self._chunks.expand_paths(path_keys or seed_keys) or pg
            except Exception as e:
                logger.warning("Postgres ltree expand failed: %s", e)
        if backend == "postgres":
            return pg
        if backend == "both":
            return _merge_expand(neo, pg)
        return neo

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
        ctx = contract_context(contract_type, title, summary)
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

        # Drop sector-specific instruments (oil & gas offshore, aviation, …) when
        # the contract context does not belong to that sector.
        if seeds and ctx:
            kept, dropped = filter_sector_mismatches(seeds, ctx)
            if dropped:
                logger.info(
                    "LegalGraphRag: dropped %s sector-mismatch seed(s) e.g. %r",
                    len(dropped),
                    (dropped[0].metadata.get("title") or dropped[0].metadata.get("doc_number") or "")[:80],
                )
            if kept:
                seeds = kept
            else:
                # All hits were niche circulars — re-seed on general labor law so
                # clauses (OT, kỷ luật, BHXH…) are not left with empty grounding.
                logger.info(
                    "LegalGraphRag: sector filter emptied seeds; recovering via Bộ luật Lao động"
                )
                recovery_q = " ".join(
                    p
                    for p in (
                        "Bộ luật Lao động",
                        (title or "").strip(),
                        (summary or "").strip()[:200],
                    )
                    if p
                )
                recovered = self._search.search(recovery_q, k=k_seed, min_score=0.0)
                kept2, _ = filter_sector_mismatches(recovered, ctx) if ctx else (recovered, [])
                seeds = kept2 or recovered[:k_seed]
        for s in seeds:
            s.metadata["role"] = "seed"

        by_path: dict[str, RetrievedChunk] = {}
        for s in seeds:
            key = _chunk_key(s.metadata)
            if key:
                by_path[key] = s
        repealed: set[str] = set()
        superseding_added = 0

        if by_path:
            seed_keys = list(by_path.keys())
            expansion = self._expand(seed_keys)
            sibling_paths = expansion.get("sibling_paths") or []
            ancestor_paths = expansion.get("ancestor_paths") or []
            parent_clause_paths = expansion.get("parent_clause_paths") or []
            related_docs = expansion.get("related_docs") or []
            repealed = set(expansion.get("repealed_by_docs") or [])

            hydrate_paths = list(
                dict.fromkeys([*sibling_paths, *ancestor_paths, *parent_clause_paths])
            )
            texts = self._chunks.get_texts_by_paths(hydrate_paths)
            meta_rows = self._chunks.get_meta_by_paths(hydrate_paths)

            for path_key, text in texts.items():
                if path_key in by_path:
                    continue
                role = "sibling" if path_key in sibling_paths else "ancestor"
                if path_key in parent_clause_paths:
                    role = "sibling"
                meta = meta_rows.get(path_key, {})
                by_path[path_key] = RetrievedChunk(
                    content=text,
                    score=None,
                    metadata={
                        "path": path_key,
                        "doc_id": meta.get("doc_id"),
                        "chunk_type": meta.get("chunk_type", "body"),
                        "doc_number": meta.get("doc_number"),
                        "title": meta.get("title"),
                        "eff_from": meta.get("eff_from"),
                        "eff_to": meta.get("eff_to"),
                        "status_flag": meta.get("status_flag"),
                        "eff_flag": meta.get("eff_flag"),
                        "root_path": meta.get("root_path"),
                        "doc_type": meta.get("doc_type"),
                        "issue_date": meta.get("issue_date"),
                        "source_element_id": meta.get("source_element_id"),
                        "source_url": meta.get("source_url"),
                        "role": role,
                    },
                )

            if related_docs:
                related_hits = self._search.search_in_docs(query, related_docs, k=2)
                for h in related_hits:
                    key = _chunk_key(h.metadata)
                    if not key or key in by_path:
                        continue
                    h.metadata["role"] = "related"
                    if h.metadata.get("doc_id") in repealed:
                        h.metadata["note"] = "source_doc_may_be_repealed"
                    by_path[key] = h

            if repealed and len(by_path) > 2:
                for _key, chunk in list(by_path.items()):
                    if chunk.metadata.get("doc_id") in repealed and chunk.metadata.get("role") == "seed":
                        chunk.metadata["note"] = "source_doc_may_be_repealed"

            superseding_added = 0
            if repealed:
                for d_id in repealed:
                    superseding_hits = self._search.search_in_docs(query, [d_id], k=2)
                    for h in superseding_hits:
                        key = _chunk_key(h.metadata)
                        if not key or key in by_path:
                            continue
                        h.metadata["role"] = "superseding"
                        h.metadata["note"] = f"replaces {d_id}"
                        by_path[key] = h
                        superseding_added += 1

        ordered = self._order_for_prompt(list(by_path.values()), as_of=as_of_date)
        if ctx:
            ordered, dropped_final = filter_sector_mismatches(ordered, ctx)
            if dropped_final:
                logger.info(
                    "LegalGraphRag: filtered %s sector-mismatch chunk(s) pre-prompt",
                    len(dropped_final),
                )
        # Prefer còn hiệu lực; drop expired chunks when any effective alternative exists.
        effective = [
            c for c in ordered if LegalGraphRag._validity_key(c, as_of_date)[0] == 0
        ]
        if effective:
            ordered = effective
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
        _SF_MAP = {
            0: "chưa xác định",
            1: "còn hiệu lực",
            2: "hết hiệu lực",
            3: "chưa có hiệu lực",
            4: "hết hiệu lực một phần",
            5: "có hiệu lực một phần",
        }
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
            ref = c.metadata.get("path") or ""
            note = c.metadata.get("note")
            status_text = c.metadata.get("eff_flag") or ""
            if not status_text:
                sf = c.metadata.get("status_flag")
                status_text = _SF_MAP.get(sf, "") if sf is not None else ""
            header = f"[{label} | {ref} | {role}]"
            if status_text:
                header += f" [{status_text}]"
            doc_type = c.metadata.get("doc_type")
            if doc_type:
                header += f" [{doc_type}]"
            issue_date = c.metadata.get("issue_date")
            if issue_date and len(issue_date) >= 4:
                header += f" [{issue_date[:4]}]"
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
    def _doc_type_rank(doc_type: str | None, title: str | None = None) -> float:
        return normative_rank(doc_type, title)

    @staticmethod
    def _as_date(value: object) -> date | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return _parse_as_of(text)
        except Exception:
            return None

    @staticmethod
    def _validity_key(chunk: RetrievedChunk, as_of: str | None = None) -> tuple[int, float, int]:
        """Return (priority, -status_rank, -year). priority 0 = usable in prompt.

        ``as_of`` may be ISO or dd/mm/yyyy (contract signing date). Always parse
        to ``date`` — never lex-compare ``15/07/2026`` against ``2025-02-15``.
        """
        sf_raw = chunk.metadata.get("status_flag")
        try:
            sf = int(sf_raw) if sf_raw is not None else 0
        except (TypeError, ValueError):
            sf = 0
        ref = _parse_as_of(as_of) if as_of else date.today()
        from_d = LegalGraphRag._as_date(chunk.metadata.get("eff_from"))
        to_d = LegalGraphRag._as_date(chunk.metadata.get("eff_to"))

        # Hard expire: status=2 OR eff_to already passed (even if VBPL cache says còn HL)
        if sf == 2 or (to_d and to_d <= ref):
            priority = 99
        elif sf == 3 or (from_d and from_d > ref):
            priority = 50  # chưa có hiệu lực
        else:
            priority = 0  # 0/? 1 còn 4/5 một phần

        rank = 0.0 if priority == 99 else _STATUS_RANK.get(sf, 0.40)

        year_val = 0
        issue_date = chunk.metadata.get("issue_date")
        for src in (issue_date, chunk.metadata.get("eff_from")):
            if isinstance(src, str) and len(src) >= 4:
                try:
                    year_val = int(src[:4])
                    break
                except ValueError:
                    continue

        return (priority, -rank, -year_val)

    @staticmethod
    def _order_for_prompt(chunks: list[RetrievedChunk], as_of: str | None = None) -> list[RetrievedChunk]:
        """Order: còn HL → cấp văn bản (Bộ luật…→TT) → status → năm → role → score."""
        role_rank = {"seed": 0, "sibling": 1, "ancestor": 2, "related": 3, "superseding": 0}
        keyed = [(c, LegalGraphRag._validity_key(c, as_of)) for c in chunks]
        keyed.sort(
            key=lambda ck: (
                ck[1][0],  # effectiveness bucket
                -LegalGraphRag._doc_type_rank(
                    ck[0].metadata.get("doc_type"),
                    ck[0].metadata.get("title"),
                ),
                ck[1][1],  # -status rank
                ck[1][2],  # -year
                role_rank.get(ck[0].metadata.get("role") or "seed", 9),
                -(ck[0].score or 0),
            )
        )
        return [c for c, _ in keyed]
