"""Extract same-document Điều/Khoản/Điểm/Chương citations → legal_path_relations."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.infrastructure.legal_corpus.muc_luc_paths import MucLucIndex, MucLucNode

# Longest-first roman (XIII before X).
_ROMAN: list[tuple[str, int]] = [
    ("XXVI", 26),
    ("XXV", 25),
    ("XXIV", 24),
    ("XXIII", 23),
    ("XXII", 22),
    ("XXI", 21),
    ("XX", 20),
    ("XIX", 19),
    ("XVIII", 18),
    ("XVII", 17),
    ("XVI", 16),
    ("XV", 15),
    ("XIV", 14),
    ("XIII", 13),
    ("XII", 12),
    ("XI", 11),
    ("IX", 9),
    ("VIII", 8),
    ("VII", 7),
    ("VI", 6),
    ("IV", 4),
    ("V", 5),
    ("III", 3),
    ("II", 2),
    ("X", 10),
    ("I", 1),
]
_ROMAN.sort(key=lambda kv: len(kv[0]), reverse=True)

# Citation points at another named instrument: "… của Luật … số 41/2019/QH14"
_EXTERNAL_AFTER = re.compile(
    r"^\s+của\s+(?:Luật|Bộ\s*luật|Nghị\s*định|Thông\s*tư|Nghị\s*quyết)"
    r"(?!\s+này\b)[^.]{0,80}?\bsố\s+\d{1,4}/\d{4}/",
    re.IGNORECASE,
)
_EXTERNAL_BEFORE = re.compile(
    r"(?:Luật|Bộ\s*luật|Nghị\s*định|Thông\s*tư|Nghị\s*quyết)"
    r"[^.]{0,60}?\bsố\s+\d{1,4}/\d{4}/[A-ZĐ0-9.\-]+\s*$",
    re.IGNORECASE,
)

_POINT_LETTER = r"[a-zđ]"
_ROMAN_OR_INT = r"(?:XXVI|XXV|XXIV|XXIII|XXII|XXI|XX|XIX|XVIII|XVII|XVI|XV|XIV|XIII|XII|XI|IX|VIII|VII|VI|IV|V|III|II|X|I|\d+)"

# Longest-first citation patterns (structural targets).
_PAT_POINT_CLAUSE_ART = re.compile(
    rf"(?:điểm|Điểm)\s*({_POINT_LETTER})\s+"
    rf"(?:khoản|Khoản)\s*(\d+)\s+"
    rf"(?:Điều|điều)\s+(\d+|này)",
    re.IGNORECASE,
)
_PAT_CLAUSE_ART = re.compile(
    rf"(?:khoản|Khoản)\s*(\d+)\s+"
    rf"(?:Điều|điều)\s+(\d+|này)",
    re.IGNORECASE,
)
_PAT_ART_RANGE = re.compile(
    r"(?:các\s+)?(?:điều|Điều)\s+từ\s+(?:Điều\s+)?(\d+)\s+đến\s+(?:Điều\s+)?(\d+)",
    re.IGNORECASE,
)
_PAT_ARTS_LIST = re.compile(
    r"(?:các\s+)?(?:điều|Điều)\s+(\d+(?:\s*,\s*\d+)+)\s+và\s+(\d+)",
    re.IGNORECASE,
)
_PAT_ART = re.compile(
    r"(?<![A-Za-zÀ-ỹ])(?:Điều|điều)\s+(\d+|này)\b",
    re.IGNORECASE,
)
_PAT_CHAPTER = re.compile(
    rf"(?<![A-Za-zÀ-ỹ])(?:Chương|chương)\s+({_ROMAN_OR_INT})\b",
    re.IGNORECASE,
)
_CLAUSE_THIS = re.compile(
    r"(?:khoản|Khoản)\s+(\d+|này)\s+(?:Điều|điều)\s+này",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class StructuralRef:
    """Unresolved structural suffix pieces (no doc root)."""

    article: int | None = None  # None = "Điều này"
    clause: int | None = None
    point: str | None = None
    chapter: int | None = None
    use_source_article: bool = False
    use_source_clause: bool = False


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").replace("\u00a0", " ")


def _roman_or_int(token: str) -> int | None:
    t = (token or "").strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    up = t.upper()
    for roman, val in _ROMAN:
        if up == roman:
            return val
    return None


def _point_token(letter: str) -> str:
    ch = (letter or "").lower()
    return "dd" if ch == "đ" else ch


def _path_root(ltree_path: str) -> str:
    """``96122.P1.C1.D14.K1`` → ``96122``."""
    return (ltree_path or "").split(".", 1)[0]


def _source_article_num(source_path: str) -> int | None:
    for p in reversed(source_path.split(".")):
        if re.fullmatch(r"D\d+", p):
            return int(p[1:])
    return None


def _source_clause_num(source_path: str) -> int | None:
    for p in reversed(source_path.split(".")):
        if re.fullmatch(r"K\d+", p):
            return int(p[1:])
    return None


def _window_has_external(text: str, start: int, end: int) -> bool:
    """Skip citations that attach to another named instrument by số hiệu."""
    after = text[end : end + 120]
    if _EXTERNAL_AFTER.search(after):
        return True
    before = text[max(0, start - 120) : start]
    if _EXTERNAL_BEFORE.search(before):
        return True
    return False


def parse_internal_refs(text: str) -> list[StructuralRef]:
    """Parse citation phrases from chunk body (same-doc only)."""
    body = _nfc(text)
    if not body:
        return []

    occupied: list[tuple[int, int]] = []
    refs: list[StructuralRef] = []

    def _claim(start: int, end: int) -> bool:
        for a, b in occupied:
            if start < b and end > a:
                return False
        occupied.append((start, end))
        return True

    def _add(m: re.Match[str], ref: StructuralRef) -> None:
        if _window_has_external(body, m.start(), m.end()):
            return
        if not _claim(m.start(), m.end()):
            return
        refs.append(ref)

    for m in _PAT_POINT_CLAUSE_ART.finditer(body):
        art_tok = m.group(3).lower()
        if art_tok == "này":
            _add(
                m,
                StructuralRef(
                    clause=int(m.group(2)),
                    point=_point_token(m.group(1)),
                    use_source_article=True,
                ),
            )
        else:
            _add(
                m,
                StructuralRef(
                    article=int(art_tok),
                    clause=int(m.group(2)),
                    point=_point_token(m.group(1)),
                ),
            )

    for m in _CLAUSE_THIS.finditer(body):
        ctok = m.group(1).lower()
        _add(
            m,
            StructuralRef(
                use_source_article=True,
                clause=None if ctok == "này" else int(ctok),
                use_source_clause=(ctok == "này"),
            ),
        )

    for m in _PAT_CLAUSE_ART.finditer(body):
        art_tok = m.group(2).lower()
        if art_tok == "này":
            _add(
                m,
                StructuralRef(clause=int(m.group(1)), use_source_article=True),
            )
        else:
            _add(
                m,
                StructuralRef(article=int(art_tok), clause=int(m.group(1))),
            )

    for m in _PAT_ART_RANGE.finditer(body):
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        if _window_has_external(body, m.start(), m.end()):
            continue
        if not _claim(m.start(), m.end()):
            continue
        for n in range(a, b + 1):
            refs.append(StructuralRef(article=n))

    for m in _PAT_ARTS_LIST.finditer(body):
        nums = [int(x) for x in re.findall(r"\d+", m.group(0))]
        if _window_has_external(body, m.start(), m.end()):
            continue
        if not _claim(m.start(), m.end()):
            continue
        for n in nums:
            refs.append(StructuralRef(article=n))

    for m in _PAT_ART.finditer(body):
        tok = m.group(1).lower()
        if tok == "này":
            _add(m, StructuralRef(use_source_article=True))
        else:
            _add(m, StructuralRef(article=int(tok)))

    for m in _PAT_CHAPTER.finditer(body):
        n = _roman_or_int(m.group(1))
        if n is None:
            continue
        _add(m, StructuralRef(chapter=n))

    return refs


def _index_by_article(index: MucLucIndex) -> dict[int, MucLucNode]:
    out: dict[int, MucLucNode] = {}
    for n in index.nodes:
        if n.level != "Article":
            continue
        leaf = n.path.rsplit(".", 1)[-1]
        m = re.fullmatch(r"D(\d+)", leaf)
        if m:
            out[int(m.group(1))] = n
    return out


def _index_by_chapter(index: MucLucIndex) -> dict[int, MucLucNode]:
    out: dict[int, MucLucNode] = {}
    for n in index.nodes:
        if n.level != "Chapter":
            continue
        leaf = n.path.rsplit(".", 1)[-1]
        m = re.fullmatch(r"C(\d+)", leaf)
        if m:
            out[int(m.group(1))] = n
    return out


def resolve_structural_ref(
    ref: StructuralRef,
    *,
    source_path: str,
    index: MucLucIndex,
    articles: dict[int, MucLucNode] | None = None,
    chapters: dict[int, MucLucNode] | None = None,
) -> str | None:
    """Return structural path (no doc root), e.g. ``P1.C3.D14.K1.a``."""
    arts = articles if articles is not None else _index_by_article(index)
    chs = chapters if chapters is not None else _index_by_chapter(index)

    if ref.chapter is not None and ref.article is None and not ref.use_source_article:
        if ref.clause is None and ref.point is None:
            node = chs.get(ref.chapter)
            return node.path if node else f"C{ref.chapter}"

    art_num = ref.article
    if ref.use_source_article or (
        art_num is None and (ref.clause is not None or ref.point is not None or ref.use_source_clause)
    ):
        art_num = _source_article_num(source_path)

    if art_num is None:
        return None

    art = arts.get(art_num)
    base = art.path if art else f"D{art_num}"

    clause_num = ref.clause
    if ref.use_source_clause:
        clause_num = _source_clause_num(source_path)

    if clause_num is None:
        return base

    clause_path = f"{base}.K{clause_num}"
    if art:
        for n in index.nodes:
            if n.level == "Clause" and n.path == clause_path:
                clause_path = n.path
                break
            if n.level == "Clause" and n.path.startswith(art.path + ".") and n.path.endswith(
                f".K{clause_num}"
            ):
                clause_path = n.path
                break

    if ref.point is None:
        return clause_path

    point_path = f"{clause_path}.{ref.point}"
    if art:
        for n in index.nodes:
            if n.level == "Point" and n.path == point_path:
                return n.path
            if (
                n.level == "Point"
                and n.path.startswith(art.path + ".")
                and n.path.endswith(f".K{clause_num}.{ref.point}")
            ):
                return n.path
    return point_path


def extract_path_relations(
    chunks: list[dict[str, Any]],
    index: MucLucIndex,
    *,
    path_root: str | None = None,
) -> list[dict[str, str]]:
    """Build ``{source_path, target_path, ref_type}`` rows from chunk texts.

    Target paths use the same ltree root as each source chunk (doc_id or doc_num).
    """
    arts = _index_by_article(index)
    chs = _index_by_chapter(index)
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for ch in chunks:
        ctype = ch.get("chunk_type") or "body"
        if ctype not in ("body", "effectivity"):
            continue
        source = ch.get("path") or ""
        text = ch.get("chunk_text") or ""
        if not source or not text:
            continue
        root = path_root or _path_root(source)
        for ref in parse_internal_refs(text):
            structural = resolve_structural_ref(
                ref,
                source_path=source,
                index=index,
                articles=arts,
                chapters=chs,
            )
            if not structural:
                continue
            target = f"{root}.{structural}" if root else structural
            if target == source:
                continue
            key = (source, target)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_path": source,
                    "target_path": target,
                    "ref_type": "dan_chieu",
                }
            )
    return rows
