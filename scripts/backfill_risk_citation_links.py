"""Enrich cached risk citations with verified legal quotes and deep links."""

from __future__ import annotations

import argparse
import json
import os
import re

import psycopg2

from app.agents.legal_citations import (
    build_source_deep_link,
    extract_article_title,
    format_path_location,
)
from app.infrastructure.legal_corpus.muc_luc_paths import chunk_ref_to_ltree


DEFAULT_DATABASE_URL = "postgresql://contractlens:contractlens@localhost:5433/contractlens"
_BRACKET_REF = re.compile(r"\[\s*[^\]|]+?\s*\|\s*([^\]]+)\]")
_BARE_REF = re.compile(r"(?<![\w])([A-Za-z0-9_-]+:[A-Za-z0-9_.]+)")
_DOC_NUMBER = re.compile(r"(?<!\d)\d{1,4}/(?:\d{4}/)?[A-ZĐ0-9.-]+", re.IGNORECASE)
_ARTICLE_TITLE = re.compile(r"Điều\s+\d+(?:\s*[.:)]\s*[^;:.]+)?", re.IGNORECASE)


def _clean_quote(text: str) -> str:
    cleaned = re.sub(r"<!--.*?-->", " ", text or "", flags=re.DOTALL)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("*", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _refs_from_risk(risk: dict) -> list[str]:
    raw = str(risk.get("legal_basis") or "")
    refs = [m.group(1).strip() for m in _BRACKET_REF.finditer(raw)]
    refs.extend(m.group(1).strip() for m in _BARE_REF.finditer(raw))
    for citation in risk.get("legal_citations") or []:
        if isinstance(citation, dict) and citation.get("evidence_path"):
            refs.append(str(citation["evidence_path"]).strip())
    normalized = []
    for ref in refs:
        path = chunk_ref_to_ltree(ref) if ":" in ref else ref
        if path:
            normalized.append(path)
    return list(dict.fromkeys(normalized))


def _citation_summary(citations: list[dict], doc_number: str) -> str:
    needle = (doc_number or "").lower()
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        title = str(citation.get("title") or "").lower()
        if needle and needle in title:
            return str(citation.get("summary") or "").strip()
    return ""


def _citation_doc_number(citation: dict) -> str | None:
    text = " ".join(
        str(citation.get(key) or "") for key in ("doc_number", "title", "summary")
    )
    match = _DOC_NUMBER.search(text)
    return match.group(0) if match else None


def _citation_article_title(citation: dict) -> str | None:
    text = " ".join(str(citation.get(key) or "") for key in ("title", "summary"))
    match = _ARTICLE_TITLE.search(text)
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else None


def _find_document(citation: dict, documents: dict[str, dict]) -> dict | None:
    doc_number = _citation_doc_number(citation)
    if doc_number and doc_number.lower() in documents:
        return documents[doc_number.lower()]

    text = " ".join(str(citation.get(key) or "") for key in ("title", "summary")).lower()
    aliases = {
        ("bộ luật lao động", "2019"): "45/2019/qh14",
        ("luật người lao động việt nam đi làm việc ở nước ngoài", "2020"): "69/2020/qh14",
    }
    for (keyword, year), number in aliases.items():
        if keyword in text and year in text and number in documents:
            return documents[number]
    return None


def backfill(database_url: str, apply: bool) -> tuple[int, int]:
    risk_count = 0
    citation_count = 0
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT contract_id, risks FROM uploaded_contracts WHERE risks IS NOT NULL"
            )
            rows = cur.fetchall()

            all_paths: set[str] = set()
            parsed_risks: dict[str, list[dict]] = {}
            for contract_id, raw_risks in rows:
                risks = raw_risks if isinstance(raw_risks, list) else []
                parsed_risks[contract_id] = risks
                for risk in risks:
                    if isinstance(risk, dict):
                        for ref in _refs_from_risk(risk):
                            all_paths.add(ref)

            metadata: dict[str, dict] = {}
            documents: dict[str, dict] = {}
            if all_paths:
                cur.execute(
                    """
                    SELECT c.path::text, c.chunk_text, c.source_element_id,
                           d.doc_num, d.title, d.source_url, d.eff_flag
                    FROM legal_embeddings c
                    JOIN legal_documents d ON d.doc_id = c.doc_id
                    WHERE c.path = ANY(%s::ltree[])
                    """,
                    (list(all_paths),),
                )
                for path, chunk_text, source_id, doc_number, title, source_url, status in cur.fetchall():
                    metadata[path] = {
                        "chunk_text": chunk_text,
                        "source_element_id": source_id,
                        "doc_number": doc_number,
                        "title": title,
                        "source_url": source_url,
                        "status": status,
                    }

            doc_numbers = {
                _citation_doc_number(citation)
                for risks in parsed_risks.values()
                for risk in risks
                if isinstance(risk, dict)
                for citation in (risk.get("legal_citations") or [])
                if isinstance(citation, dict)
            }
            doc_numbers.discard(None)
            documents: dict[str, dict] = {}
            cur.execute(
                """
                SELECT doc_num, title, source_url, eff_flag
                FROM legal_documents
                WHERE LOWER(doc_num) = ANY(%s::text[])
                   OR title ILIKE '%%Bộ luật Lao động%%'
                   OR title ILIKE '%%Luật Người lao động Việt Nam đi làm việc ở nước ngoài%%'
                """,
                ([number.lower() for number in doc_numbers] or [""],),
            )
            for doc_number, title, source_url, status in cur.fetchall():
                key = str(doc_number).lower()
                current = documents.get(key)
                if current is None or (not current.get("source_url") and source_url):
                    documents[key] = {
                        "doc_number": doc_number,
                        "title": title,
                        "source_url": source_url,
                        "status": status,
                    }

            for contract_id, risks in parsed_risks.items():
                changed = False
                for risk in risks:
                    if not isinstance(risk, dict):
                        continue
                    refs = _refs_from_risk(risk)
                    old_citations = risk.get("legal_citations") or []
                    if not refs and not isinstance(old_citations, list):
                        continue
                    enriched = []
                    for ref in refs:
                        path = ref
                        item = metadata.get(path)
                        if not item:
                            continue
                        quote_text = _clean_quote(item["chunk_text"])
                        location = format_path_location(path)
                        article_title = extract_article_title(item["chunk_text"])
                        enriched.append(
                            {
                                "title": item["title"] or item["doc_number"] or "Căn cứ pháp lý",
                                "summary": _citation_summary(old_citations, item["doc_number"]),
                                "doc_number": item["doc_number"],
                                "location": location.get("location"),
                                "article": location.get("article"),
                                "clause": location.get("clause"),
                                "point": location.get("point"),
                                "quote": quote_text,
                                "source_url": item["source_url"],
                                "deep_link": build_source_deep_link(
                                    item["source_url"],
                                    item["source_element_id"],
                                    article_title or location.get("article") or quote_text,
                                ),
                                "source_element_id": item["source_element_id"],
                                "evidence_path": path,
                                "status": item["status"],
                            }
                        )
                    if isinstance(old_citations, list):
                        represented = {
                            str(item.get("doc_number") or "").lower()
                            for item in enriched
                            if item.get("doc_number")
                        }
                        for citation in old_citations:
                            if not isinstance(citation, dict):
                                continue
                            evidence_path = str(citation.get("evidence_path") or "").strip()
                            doc_number = _citation_doc_number(citation)
                            if evidence_path and evidence_path in refs:
                                continue
                            if doc_number and doc_number.lower() in represented:
                                continue
                            document = _find_document(citation, documents)
                            enriched_citation = dict(citation)
                            if document and document["source_url"]:
                                enriched_citation.update(
                                    {
                                        "doc_number": document["doc_number"],
                                        "source_url": document["source_url"],
                                        "deep_link": build_source_deep_link(
                                            document["source_url"],
                                            None,
                                            _citation_article_title(citation) or "Điều",
                                        ),
                                        "status": document["status"],
                                    }
                                )
                            enriched.append(enriched_citation)
                    if enriched and old_citations != enriched:
                        risk["legal_citations"] = enriched
                        changed = True
                        citation_count += len(enriched)
                if changed:
                    risk_count += 1
                    if apply:
                        cur.execute(
                            "UPDATE uploaded_contracts SET risks = %s::jsonb, updated_at = NOW() WHERE contract_id = %s",
                            (json.dumps(risks, ensure_ascii=False), contract_id),
                        )
        if not apply:
            conn.rollback()
    return risk_count, citation_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write enriched citations; default is dry-run")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    args = parser.parse_args()
    risks, citations = backfill(args.database_url, args.apply)
    mode = "updated" if args.apply else "would update"
    print(f"{mode} {citations} citation(s) across {risks} risk item(s)")


if __name__ == "__main__":
    main()
