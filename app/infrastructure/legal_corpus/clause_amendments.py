"""Parse clause_amendments.json → legal_path_relations rows (ltree by doc_num).

Paths use sanitized số hiệu as root label (e.g. ``100_2015_QH13.P2.C2.D134.K1.g``),
not portal doc_id, so RAG / logs stay human-readable.

Edge direction: sourceProvision (VB sửa) → targetProvision (điều khoản bị tác động).
Same-doc and cross-doc both land in ``legal_path_relations``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.infrastructure.legal_corpus.muc_luc_paths import (
    build_muc_luc_index,
    sanitize_doc_id_for_ltree,
)
from app.infrastructure.legal_corpus.thuoc_tinh_mapper import map_thuoc_tinh

# VBPL provision-amendment ``type`` on sourceProvisions (partial; extend as crawled).
# Aligned where possible with scripts/crawl_vbpl/convert.REFERENCE_TYPE_NAMES.
CLAUSE_AMEND_TYPE_TO_REF: dict[int, str] = {
    1: "bai_bo",  # bãi bỏ (chương/điều/…)
    3: "can_cu",
    10: "sua_doi",  # sửa đổi / bỏ từ / chỉnh nội dung
}

_DOC_NUM_IN_TITLE = re.compile(
    r"s[oố]\s+([0-9]+/[0-9]+/[A-Za-z0-9À-ỹĐđ\-]+)",
    re.IGNORECASE,
)
_DIEU = re.compile(r"(?:Điều|ĐIỀU)\s+(\d+)", re.I)
_KHOAN = re.compile(r"(?:Khoản|KHOẢN)\s+(\d+)", re.I)
_DIEM = re.compile(r"(?:Điểm|ĐIỂM)\s*([a-zA-ZđĐ])", re.I)
_CHUONG = re.compile(r"(?:Chương|CHƯƠNG)\s+([IVXLC\d]+)", re.I)
_PHAN = re.compile(r"(?:Phần|PHẦN)\s+(?:Thứ\s+)?([IVXLC\d]+|[A-Za-zÀ-ỹ]+)", re.I)
_ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
}
_VI_ORDINAL = {
    "nhat": 1,
    "nhất": 1,
    "hai": 2,
    "ba": 3,
    "tu": 4,
    "tư": 4,
    "nam": 5,
    "năm": 5,
    "sau": 6,
    "sáu": 6,
    "bay": 7,
    "bảy": 7,
    "tam": 8,
    "tám": 8,
    "chin": 9,
    "chín": 9,
    "muoi": 10,
    "mười": 10,
}


@dataclass(frozen=True, slots=True)
class PathRelationRow:
    source_path: str
    target_path: str
    ref_type: str
    source_doc_id: str | None = None
    target_doc_id: str | None = None
    source_doc_num: str | None = None
    target_doc_num: str | None = None
    note: str | None = None


def sanitize_doc_num_for_ltree(doc_num: str) -> str:
    """``100/2015/QH13`` → ``100_2015_QH13`` (same rules as legal_documents.path)."""
    return sanitize_doc_id_for_ltree(doc_num)


def to_doc_num_ltree(doc_num: str, structural: str | None) -> str | None:
    root = sanitize_doc_num_for_ltree(doc_num)
    if not structural:
        return root or None
    struct = structural.strip().lstrip(".")
    if not struct:
        return root or None
    return f"{root}.{struct}"


def ref_type_from_amend_type(type_code: Any) -> str:
    if type_code is None:
        return "sua_doi"
    try:
        code = int(type_code)
    except (TypeError, ValueError):
        return f"loai_{type_code}"
    return CLAUSE_AMEND_TYPE_TO_REF.get(code, f"loai_{code}")


def doc_num_from_title_document(title_document: str | None) -> str | None:
    if not title_document:
        return None
    m = _DOC_NUM_IN_TITLE.search(title_document)
    return m.group(1).strip() if m else None


def _roman_or_int(token: str) -> int | None:
    t = (token or "").strip()
    if t.isdigit():
        return int(t)
    up = t.upper()
    if up in _ROMAN:
        return _ROMAN[up]
    return _VI_ORDINAL.get(t.lower())


def structural_path_from_provision_title(title: str | None) -> str | None:
    """Best-effort parse ``Điểm b, Khoản 1, Điều 177, …`` → ``D177.K1.b``."""
    if not title:
        return None
    parts: list[str] = []
    m = _PHAN.search(title)
    if m:
        n = _roman_or_int(m.group(1))
        if n is not None:
            parts.append(f"P{n}")
    m = _CHUONG.search(title)
    if m:
        n = _roman_or_int(m.group(1))
        if n is not None:
            parts.append(f"C{n}")
    m = _DIEU.search(title)
    if m:
        parts.append(f"D{int(m.group(1))}")
    m = _KHOAN.search(title)
    if m:
        parts.append(f"K{int(m.group(1))}")
    m = _DIEM.search(title)
    if m:
        ch = m.group(1).lower()
        parts.append("dd" if ch == "đ" else ch)
    return ".".join(parts) if parts else None


def _strip_doc_prefix(ltree_path: str) -> str:
    """``96122.C2.D134.K1.g`` → ``C2.D134.K1.g``."""
    if not ltree_path or "." not in ltree_path:
        return ltree_path
    return ltree_path.split(".", 1)[1]


def resolve_structural_from_embeddings(
    doc_id: str,
    *,
    title: str | None,
    embedding_paths: list[str] | None,
) -> str | None:
    """Match a provision against embedding paths (doc_id-prefixed) → structural suffix."""
    if not embedding_paths:
        return structural_path_from_provision_title(title)
    guessed = structural_path_from_provision_title(title)
    suffixes = [_strip_doc_prefix(p) for p in embedding_paths if p]
    if guessed:
        # Prefer exact suffix match, then suffix endswith guessed (embeddings often omit Part)
        for s in suffixes:
            if s == guessed or s.endswith("." + guessed) or s.endswith(guessed):
                return s
        # guessed may include P/C that embeddings skip
        g_parts = guessed.split(".")
        for start in range(len(g_parts)):
            sub = ".".join(g_parts[start:])
            for s in suffixes:
                if s == sub or s.endswith("." + sub):
                    return s
    return guessed


@dataclass
class DocNumResolver:
    """Resolve portal doc_id → số hiệu (doc_num)."""

    by_doc_id: dict[str, str]

    def resolve(
        self,
        doc_id: str | None,
        *,
        title_document: str | None = None,
        fallback_doc_num: str | None = None,
    ) -> str | None:
        if doc_id and doc_id in self.by_doc_id:
            return self.by_doc_id[doc_id]
        parsed = doc_num_from_title_document(title_document)
        if parsed:
            return parsed
        return fallback_doc_num


def parse_clause_amendments(
    amendments: dict[str, Any],
    *,
    muc_luc: list[dict[str, Any]],
    target_doc_id: str,
    target_doc_num: str,
    doc_num_resolver: DocNumResolver,
    embedding_paths_by_doc: dict[str, list[str]] | None = None,
) -> tuple[list[PathRelationRow], list[str]]:
    """Extract non-null amendments into path relation rows.

    Returns (rows, warnings).
    """
    index = build_muc_luc_index(muc_luc)
    emb = embedding_paths_by_doc or {}
    rows: list[PathRelationRow] = []
    warnings: list[str] = []

    for key, payload in amendments.items():
        if not payload or not isinstance(payload, dict):
            continue
        target = payload.get("targetProvision") or {}
        target_id = str(target.get("id") or key)
        structural = index.id_to_path.get(target_id)
        if not structural:
            warnings.append(f"target muc_luc id not found: {target_id}")
            continue
        target_path = to_doc_num_ltree(target_doc_num, structural)
        if not target_path:
            warnings.append(f"bad target path for {target_id}")
            continue

        sources = payload.get("sourceProvisions") or []
        if not sources:
            warnings.append(f"no sourceProvisions for target {target_id}")
            continue

        for src in sources:
            if not isinstance(src, dict):
                continue
            src_doc_id = str(src.get("documentId") or "") or None
            src_doc_num = doc_num_resolver.resolve(
                src_doc_id,
                title_document=src.get("titleDocument"),
            )
            if not src_doc_num:
                warnings.append(
                    f"cannot resolve doc_num for source doc_id={src_doc_id!r} "
                    f"titleDocument={src.get('titleDocument')!r}"
                )
                continue

            # Same-doc: prefer local muc_luc if source id is present
            src_id = str(src.get("id") or "")
            src_structural = index.id_to_path.get(src_id) if src_id else None
            if not src_structural:
                src_structural = resolve_structural_from_embeddings(
                    src_doc_id or "",
                    title=src.get("title"),
                    embedding_paths=emb.get(src_doc_id or "", []),
                )
            if not src_structural:
                warnings.append(
                    f"cannot resolve source structural title={src.get('title')!r} "
                    f"doc={src_doc_id}"
                )
                continue

            source_path = to_doc_num_ltree(src_doc_num, src_structural)
            if not source_path:
                continue

            rows.append(
                PathRelationRow(
                    source_path=source_path,
                    target_path=target_path,
                    ref_type=ref_type_from_amend_type(src.get("type")),
                    source_doc_id=src_doc_id,
                    target_doc_id=target_doc_id,
                    source_doc_num=src_doc_num,
                    target_doc_num=target_doc_num,
                    note=(src.get("content") or None),
                )
            )

    # de-dupe by UK key
    seen: set[tuple[str, str, str]] = set()
    unique: list[PathRelationRow] = []
    for r in rows:
        k = (r.source_path, r.target_path, r.ref_type)
        if k in seen:
            continue
        seen.add(k)
        unique.append(r)
    return unique, warnings


def load_clause_amendments_folder(
    folder: Path | str,
    *,
    doc_num_resolver: DocNumResolver | None = None,
    embedding_paths_by_doc: dict[str, list[str]] | None = None,
) -> tuple[list[PathRelationRow], list[str], dict[str, Any]]:
    """Load folder artifacts and parse amendments. Skips if file missing/empty."""
    folder = Path(folder)
    amend_path = folder / "clause_amendments.json"
    meta: dict[str, Any] = {"folder": str(folder), "skipped": False}
    if not amend_path.is_file():
        meta["skipped"] = True
        meta["reason"] = "no clause_amendments.json"
        return [], [], meta

    amendments = json.loads(amend_path.read_text(encoding="utf-8"))
    if not isinstance(amendments, dict):
        meta["skipped"] = True
        meta["reason"] = "clause_amendments.json is not an object"
        return [], [], meta

    thuoc_tinh = map_thuoc_tinh(
        json.loads((folder / "thuoc_tinh.json").read_text(encoding="utf-8"))
    )
    muc_luc = json.loads((folder / "muc_luc.json").read_text(encoding="utf-8"))
    if not isinstance(muc_luc, list):
        muc_luc = list(muc_luc.get("children") or []) if isinstance(muc_luc, dict) else []

    target_doc_id = str(thuoc_tinh["doc_id"])
    target_doc_num = str(thuoc_tinh.get("doc_num") or "")
    if not target_doc_num:
        meta["skipped"] = True
        meta["reason"] = "missing doc_num in thuoc_tinh"
        return [], [], meta

    resolver = doc_num_resolver or DocNumResolver(by_doc_id={target_doc_id: target_doc_num})
    # Ensure local doc always resolves
    if target_doc_id not in resolver.by_doc_id:
        resolver.by_doc_id[target_doc_id] = target_doc_num

    rows, warnings = parse_clause_amendments(
        amendments,
        muc_luc=muc_luc,
        target_doc_id=target_doc_id,
        target_doc_num=target_doc_num,
        doc_num_resolver=resolver,
        embedding_paths_by_doc=embedding_paths_by_doc,
    )
    meta.update(
        {
            "doc_id": target_doc_id,
            "doc_num": target_doc_num,
            "amendment_keys": len(amendments),
            "relation_count": len(rows),
            "warning_count": len(warnings),
        }
    )
    return rows, warnings, meta


def upsert_path_relations(rows: list[PathRelationRow]) -> int:
    """Insert into legal_path_relations; return inserted attempt count (ON CONFLICT skip)."""
    if not rows:
        return 0
    from app.infrastructure.db.connection import get_db

    n = 0
    with get_db() as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO legal_path_relations (source_path, target_path, ref_type)
                    VALUES (%s::ltree, %s::ltree, %s)
                    ON CONFLICT (source_path, target_path, ref_type) DO NOTHING
                    """,
                    (r.source_path, r.target_path, r.ref_type),
                )
                n += cur.rowcount or 0
    return n


def load_doc_num_map_from_db() -> dict[str, str]:
    from app.infrastructure.db.connection import get_db

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, doc_num FROM legal_documents "
                "WHERE doc_num IS NOT NULL AND doc_num <> ''"
            )
            return {str(r[0]): str(r[1]) for r in cur.fetchall()}


def load_embedding_paths_for_docs(doc_ids: list[str]) -> dict[str, list[str]]:
    if not doc_ids:
        return {}
    from app.infrastructure.db.connection import get_db

    out: dict[str, list[str]] = {d: [] for d in doc_ids}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, path::text FROM legal_embeddings "
                "WHERE doc_id = ANY(%s)",
                (list(doc_ids),),
            )
            for doc_id, path in cur.fetchall():
                out.setdefault(str(doc_id), []).append(str(path))
    return out
