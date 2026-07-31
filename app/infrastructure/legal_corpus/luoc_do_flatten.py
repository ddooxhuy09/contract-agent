"""Flatten crawler luoc_do.json into doc↔doc relation rows + stub metadata."""

from __future__ import annotations

from typing import Any


def flatten_luoc_do(raw: dict[str, Any] | None) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    """Return (relations, stub_docs_by_id).

    Outgoing ``relations``: from this doc → related doc.
    Incoming ``relations_incoming``: related doc → this doc (direction flipped).
    """
    if not raw:
        return [], {}

    doc_id = str(raw.get("doc_id") or "")
    relations: list[dict[str, str]] = []
    stubs: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str, str]] = set()

    def _remember(doc: dict[str, Any]) -> str:
        oid = str(doc.get("doc_id") or "")
        if not oid:
            return ""
        if oid not in stubs:
            stubs[oid] = {
                "doc_id": oid,
                "doc_num": str(doc.get("doc_num") or oid),
                "title": str(doc.get("title") or f"Stub {oid}"),
                "doc_type": str(doc.get("doc_type") or "Unknown"),
                "issue_date": doc.get("issue_date"),
                "eff_from": doc.get("eff_from"),
                "eff_to": doc.get("eff_to"),
                "status_flag": 0,
            }
        return oid

    def _add(from_id: str, to_id: str, rel_type: str) -> None:
        if not from_id or not to_id or not rel_type:
            return
        key = (from_id, to_id, rel_type)
        if key in seen:
            return
        seen.add(key)
        relations.append(
            {
                "from_doc_id": from_id,
                "to_doc_id": to_id,
                "relation_type": rel_type,
            }
        )

    for rel_type, bucket in (raw.get("relations") or {}).items():
        for doc in (bucket or {}).get("documents") or []:
            other = _remember(doc)
            _add(doc_id, other, str(rel_type))

    for rel_type, bucket in (raw.get("relations_incoming") or {}).items():
        for doc in (bucket or {}).get("documents") or []:
            other = _remember(doc)
            # Incoming edge of type T means other --T--> this doc
            _add(other, doc_id, str(rel_type))

    return relations, stubs
