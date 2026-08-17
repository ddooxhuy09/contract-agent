"""Normalize legal citations into complete document entities (never split on /)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from app.schemas.contract import LegalCitation

# Atomic VN legal document number, e.g. 20/2023/TT-BCT, 145/2020/NĐ-CP, 45/2019/QH14
# (?<!\d) prevents matching "0/2023/..." inside "20/2023/..."
_DOC_NUM = r"(?<!\d)\d{1,4}/\d{4}/[A-ZĐ0-9.-]+"

_PREFIX = (
    r"(?:Thông\s*tư|Nghị\s*định|Quyết\s*định|Luật|Bộ\s*luật|Chỉ\s*thị|"
    r"Nghị\s*quyết|Thông\s*báo|Công\s*văn)\s+"
)

# Start of a citation entity in free text
_CITATION_START = re.compile(
    rf"(?:{_PREFIX})?{_DOC_NUM}|Điều\s+\d+(?:\s+(?:Bộ\s+)?luật[^\n\[\]:;.]{{0,40}})?",
    re.IGNORECASE,
)

_CHUNK_REF_IN_BRACKETS = re.compile(r"\[\s*([^\]|]+?)\s*\|\s*[^\]]+\]")
_BARE_CHUNK_REF = re.compile(r"\b\d{3,}:[A-Za-z0-9.]+\b")


def strip_internal_refs(text: str) -> str:
    """Remove chunk_ref / internal ids; keep human-readable doc numbers."""
    s = _CHUNK_REF_IN_BRACKETS.sub(lambda m: m.group(1).strip(), text or "")
    s = _BARE_CHUNK_REF.sub("", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    return s.strip()


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                t = item.get("text") or item.get("point") or item.get("summary")
                if isinstance(t, str) and t.strip():
                    out.append(t.strip())
        return out
    return []


def citations_from_llm(value: Any) -> list[LegalCitation]:
    """Map LLM legal_citations array → LegalCitation(title, summary)."""
    if not value or not isinstance(value, list):
        return []
    out: list[LegalCitation] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = (
            item.get("title")
            or item.get("label")
            or item.get("name")
            or item.get("doc_number")
            or ""
        )
        title = strip_internal_refs(str(title)).strip()
        if not title:
            continue
        summary = item.get("summary")
        if summary is None:
            points = _as_str_list(item.get("points") or item.get("bullets") or [])
            summary = " ".join(points)
        summary = strip_internal_refs(str(summary or "")).strip()
        out.append(
            LegalCitation(
                title=title,
                summary=summary,
                doc_number=str(item.get("doc_number") or "").strip() or None,
                location=str(item.get("location") or "").strip() or None,
            )
        )
    return out


def citations_from_legal_basis_text(raw: str | None) -> list[LegalCitation]:
    """
    Structure a free-text legal_basis into complete citation entities.

    Uses document-number boundaries that cannot split inside '20/2023/TT-BCT'
    (unlike a naive \\d{1,3}/\\d{4}/ lookahead).
    """
    text = strip_internal_refs(raw or "")
    if not text:
        return []

    matches = list(_CITATION_START.finditer(text))
    if not matches:
        return [LegalCitation(title="Căn cứ pháp lý", summary=text)]

    citations: list[LegalCitation] = []
    for i, m in enumerate(matches):
        title = m.group(0).strip().rstrip(" :—–-")
        start_body = m.end()
        end_body = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start_body:end_body].strip()
        body = re.sub(r"^[\s:.—–\-]+", "", body).strip()
        # Drop trailing separators before next citation
        body = re.sub(r"[\s.;]+$", "", body).strip()
        citations.append(LegalCitation(title=title, summary=body))

    return citations


def resolve_legal_citations(
    llm_citations: Any,
    legal_basis: str | None,
) -> list[LegalCitation]:
    """Prefer structured LLM output; else structure legal_basis on the backend."""
    structured = citations_from_llm(llm_citations)
    if structured:
        return structured
    return citations_from_legal_basis_text(legal_basis)


def citations_to_legal_basis_line(citations: list[LegalCitation]) -> str | None:
    if not citations:
        return None
    parts = []
    for c in citations:
        if c.summary:
            parts.append(f"{c.title}: {c.summary}")
        else:
            parts.append(c.title)
    return "; ".join(parts) or None


_PATH_TOKEN = re.compile(r"^(C|M|TM|D|K)(\d+)$", re.IGNORECASE)
_POINT_TOKEN = re.compile(r"^[a-zđ]+$", re.IGNORECASE)


def format_path_location(path: str | None) -> dict[str, str | None]:
    """Turn the persisted ltree path into human-readable legal coordinates."""
    parts = (path or "").split(".")
    values: dict[str, str | None] = {
        "chapter": None,
        "section": None,
        "article": None,
        "clause": None,
        "point": None,
    }
    labels: list[str] = []
    for token in parts:
        match = _PATH_TOKEN.match(token)
        if match:
            prefix, number = match.groups()
            prefix = prefix.upper()
            if prefix == "C":
                values["chapter"] = f"Chương {number}"
                labels.append(values["chapter"])
            elif prefix == "M":
                values["section"] = f"Mục {number}"
                labels.append(values["section"])
            elif prefix == "TM":
                values["section"] = f"Tiểu mục {number}"
                labels.append(values["section"])
            elif prefix == "D":
                values["article"] = f"Điều {number}"
                labels.append(values["article"])
            elif prefix == "K":
                values["clause"] = f"Khoản {number}"
                labels.append(values["clause"])
        elif values["clause"] and _POINT_TOKEN.match(token):
            values["point"] = f"Điểm {token}"
            labels.append(values["point"])
    values["location"] = " > ".join(labels) or None
    return values


def _clean_quote(text: str) -> str:
    """Remove corpus-only Markdown markers while keeping the legal wording."""
    cleaned = re.sub(r"<!--.*?-->", " ", text or "", flags=re.DOTALL)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("*", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_article_title(text: str | None) -> str | None:
    """Return the visible Điều heading used by VBPL's table of contents."""
    cleaned = re.sub(r"<!--.*?-->", " ", text or "", flags=re.DOTALL)
    cleaned = cleaned.replace("**", "").replace("__", "").replace("*", "")
    for line in cleaned.splitlines():
        line = re.sub(r"^\s*#+\s*", "", line).strip()
        if re.match(r"^Điều\s+\d+\s*[.:)]\s*\S", line, re.IGNORECASE):
            return re.sub(r"\s+", " ", line).strip()
    return None


def _fragment_quote(text: str, max_chars: int = 180) -> str:
    """Choose a short exact visible prefix so links stay within browser URL limits."""
    cleaned = _clean_quote(text)
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars]
    boundary = max(cut.rfind("."), cut.rfind(";"), cut.rfind(" "))
    return cut[: boundary if boundary >= 60 else max_chars].strip()


def build_text_fragment_url(source_url: str | None, quote_text: str | None) -> str | None:
    """Build a standards-based Scroll-to-Text Fragment URL."""
    if not source_url or not quote_text:
        return None
    parsed = urlsplit(source_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = _toan_van_query(parsed.query)
    fragment_quote = _fragment_quote(quote_text)
    if not fragment_quote:
        return None
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, query, f":~:text={quote(fragment_quote, safe='')}" )
    )


def _toan_van_query(query: str) -> str:
    """Always open the rendered full-text tab before applying an anchor."""
    values = [(key, value) for key, value in parse_qsl(query, keep_blank_values=True) if key != "tabs"]
    values.append(("tabs", "toan-van"))
    return urlencode(values)


def build_source_deep_link(
    source_url: str | None,
    source_element_id: str | None,
    quote_text: str | None,
) -> str | None:
    """Prefer VBPL's real DOM anchor; text fragments are the fallback."""
    if source_url and source_element_id:
        parsed = urlsplit(source_url.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    _toan_van_query(parsed.query),
                    quote(str(source_element_id).strip(), safe="-._~"),
                )
            )
    return build_text_fragment_url(source_url, quote_text)


def _doc_meta(doc: Any) -> tuple[dict, str]:
    if isinstance(doc, dict):
        meta = dict(doc.get("metadata") or doc)
        content = doc.get("content") or doc.get("page_content") or ""
        return meta, str(content)
    return dict(getattr(doc, "metadata", {}) or {}), str(getattr(doc, "page_content", "") or "")


def _citation_status(meta: dict, as_of: str | date | None = None) -> str | None:
    """Prefer as_of + dates over stale VBPL ``eff_flag`` cache."""
    from app.agents.labor_code_resolver import _parse_as_of

    ref = _parse_as_of(as_of)
    try:
        sf = int(meta.get("status_flag")) if meta.get("status_flag") is not None else None
    except (TypeError, ValueError):
        sf = None
    eff_to_raw = meta.get("eff_to")
    eff_from_raw = meta.get("eff_from")
    try:
        to_d = _parse_as_of(str(eff_to_raw)[:10]) if eff_to_raw else None
    except Exception:
        to_d = None
    try:
        from_d = _parse_as_of(str(eff_from_raw)[:10]) if eff_from_raw else None
    except Exception:
        from_d = None
    if sf == 2 or (to_d and to_d <= ref):
        return "Hết hiệu lực"
    if sf == 3 or (from_d and from_d > ref):
        return "Chưa có hiệu lực"
    if sf == 4:
        return "Hết hiệu lực một phần"
    if sf == 5:
        return "Còn hiệu lực một phần"
    cached = str(meta.get("eff_flag") or "").strip()
    if cached:
        return cached
    if sf == 1:
        return "Còn hiệu lực"
    return None


def _article_key(meta: dict, location: dict) -> str:
    doc = str(meta.get("doc_number") or meta.get("title") or "").strip().lower()
    article = str(location.get("article") or "").strip().lower()
    return f"{doc}|{article}"


def ground_citations(
    llm_citations: Any,
    evidence_paths: Any,
    docs: list[Any],
    *,
    contract_text: str | None = None,
    as_of_date: str | None = None,
    max_citations: int = 4,
) -> list[LegalCitation]:
    """Attach citations only to retrieved documents, preserving legacy fallback.

    Drops sector-mismatched docs, recomputes status vs ``as_of_date``, and
    dedupes to one citation per (doc, article) so sibling điểm floods don't
    dominate the UI.
    """
    from app.infrastructure.retrieval.scope_match import (
        doc_scope_text,
        is_sector_mismatch,
    )

    parsed = citations_from_llm(llm_citations)
    by_path: dict[str, tuple[dict, str]] = {}
    for doc in docs:
        meta, content = _doc_meta(doc)
        if contract_text and is_sector_mismatch(doc_scope_text(meta, content), contract_text):
            continue
        path = str(meta.get("path") or "").strip()
        if path:
            by_path[path] = (meta, content)

    requested = [str(p).strip() for p in (evidence_paths or []) if str(p).strip()]
    selected: list[tuple[dict, str, LegalCitation | None]] = []
    for path in requested:
        item = by_path.get(path)
        if item:
            selected.append((item[0], item[1], None))

    if not selected and parsed:
        for citation in parsed:
            needle = (citation.doc_number or citation.title).lower()
            for meta, content in by_path.values():
                doc_number = str(meta.get("doc_number") or "").lower()
                title = str(meta.get("title") or "").lower()
                if (doc_number and doc_number in needle) or (needle and needle in title):
                    selected.append((meta, content, citation))
                    break

    if not selected:
        # Still filter parsed LLM cites that name sector-mismatched instruments.
        if contract_text and parsed:
            filtered = []
            for c in parsed:
                blob = f"{c.title or ''} {c.doc_number or ''} {c.summary or ''}"
                if not is_sector_mismatch(blob, contract_text):
                    filtered.append(c)
            return filtered
        return parsed

    grounded: list[LegalCitation] = []
    seen_articles: set[str] = set()
    for meta, content, matched in selected:
        path = str(meta.get("path") or "")
        location = format_path_location(path)
        quote_text = _clean_quote(content)
        if not quote_text:
            continue
        key = _article_key(meta, location)
        if key in seen_articles:
            continue
        seen_articles.add(key)
        title = str(meta.get("title") or (matched.title if matched else "Căn cứ pháp lý"))
        summary = matched.summary if matched else ""
        doc_number = str(meta.get("doc_number") or "").strip() or None
        source_url = str(meta.get("source_url") or "").strip() or None
        grounded.append(
            LegalCitation(
                title=title,
                summary=summary,
                doc_number=doc_number,
                location=location["location"],
                article=location["article"],
                clause=location["clause"],
                point=location["point"],
                quote=quote_text,
                source_url=source_url,
                deep_link=build_source_deep_link(
                    source_url,
                    str(meta.get("source_element_id") or "").strip() or None,
                    extract_article_title(content) or location["article"] or quote_text,
                ),
                source_element_id=str(meta.get("source_element_id") or "").strip() or None,
                evidence_path=path or None,
                status=_citation_status(meta, as_of_date),
            )
        )
        if len(grounded) >= max_citations:
            break
    return grounded or parsed
