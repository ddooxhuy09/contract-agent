"""Normalize legal citations into complete document entities (never split on /)."""

from __future__ import annotations

import re
from typing import Any

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
        out.append(LegalCitation(title=title, summary=summary))
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
