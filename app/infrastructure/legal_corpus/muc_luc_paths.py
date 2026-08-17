"""Build structural paths and graph nodes from muc_luc.json."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

_LEVEL_PREFIX = {
    "Part": "P",
    "Chapter": "C",
    "Section": "M",
    "SubSection": "TM",
    "Article": "D",
    "Clause": "K",
    "Appendix": "PL",
    "Group": "N",
}

_NUM_RE = re.compile(r"(\d+)", re.UNICODE)
_POINT_RE = re.compile(r"(?:Điểm|ĐIỂM)\s*([a-zA-ZđĐ])", re.UNICODE)

# Longest-first roman match (IX before I, XIII before X, …). Cover Chương I–L.
_ROMAN_VALUES: list[tuple[str, int]] = [
    ("L", 50),
    ("XL", 40),
    ("XXXIX", 39),
    ("XXXVIII", 38),
    ("XXXVII", 37),
    ("XXXVI", 36),
    ("XXXV", 35),
    ("XXXIV", 34),
    ("XXXIII", 33),
    ("XXXII", 32),
    ("XXXI", 31),
    ("XXX", 30),
    ("XXIX", 29),
    ("XXVIII", 28),
    ("XXVII", 27),
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
# Sort by roman length desc so XIII wins over X/I
_ROMAN_VALUES.sort(key=lambda kv: len(kv[0]), reverse=True)

_VI_ORDINAL = {
    "nhat": 1,
    "nhất": 1,
    "hai": 2,
    "ba": 3,
    "bon": 4,
    "bốn": 4,
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

# Capture number token right after level keyword when present.
_LEVEL_NUM_RE = {
    "Part": re.compile(
        r"(?:Phần|PHẦN)\s+(?:Thứ\s+)?([IVXLCDM\d]+|[A-Za-zÀ-ỹ]+)",
        re.IGNORECASE,
    ),
    "Chapter": re.compile(
        r"(?:Chương|CHƯƠNG)\s+([IVXLCDM\d]+)",
        re.IGNORECASE,
    ),
    "Section": re.compile(
        r"(?:Mục|MỤC)\s+([IVXLCDM\d]+)",
        re.IGNORECASE,
    ),
    "SubSection": re.compile(
        r"(?:Tiểu\s*mục|TIỂU\s*MỤC)\s+([IVXLCDM\d]+)",
        re.IGNORECASE,
    ),
    "Article": re.compile(r"(?:Điều|ĐIỀU)\s+(\d+)", re.IGNORECASE),
    "Clause": re.compile(r"(?:Khoản|KHOẢN)\s+(\d+)", re.IGNORECASE),
}


def _parse_roman_or_int(token: str) -> int | None:
    t = (token or "").strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    up = t.upper()
    for roman, val in _ROMAN_VALUES:
        if up == roman:
            return val
    return _VI_ORDINAL.get(t.lower())


def _point_letter(title: str) -> str | None:
    """Return point leaf (a, b, …, dd) only when title has a single letter after Điểm."""
    m = _POINT_RE.search(title)
    if not m:
        return None
    # Reject multi-word junk like "Điểm khoan"
    after = title[m.start() :]
    m_full = re.match(r"(?:Điểm|ĐIỂM)\s*([a-zA-ZđĐ])(?:\s|$|[).,;:])", after, re.I)
    if not m_full:
        # allow bare "Điểm đ" end of string
        m_full = re.fullmatch(r"(?:Điểm|ĐIỂM)\s*([a-zA-ZđĐ])", title.strip(), re.I)
    if not m_full:
        return None
    ch = m_full.group(1).lower()
    return "dd" if ch == "đ" else ch


def _id_token(prefix: str, nid: str, sibling_index: int) -> str:
    """Stable unique ltree label when title has no reliable number/letter."""
    cleaned = re.sub(r"[^A-Za-z0-9]", "", nid or "")[:10]
    if cleaned:
        return f"{prefix}_{cleaned}"
    return f"{prefix}_u{sibling_index + 1}"


def _segment_token(level: str, title: str, sibling_index: int) -> str | None:
    """Build path segment from title, or None if title is unreliable (caller unique-ifies)."""
    prefix = _LEVEL_PREFIX.get(level)
    if level == "Point":
        return _point_letter(title)
    if prefix is None:
        return None

    # 1) Prefer number right after the level keyword (Phần Thứ Hai, Chương XIII, …)
    level_re = _LEVEL_NUM_RE.get(level)
    if level_re:
        m = level_re.search(title)
        if m:
            raw = m.group(1).strip()
            # Article/Clause/Part keyword present but capture is empty / non-numeric word
            # without ordinal — treat as weak (e.g. title == "Điều")
            n = _parse_roman_or_int(raw)
            if n is not None:
                return f"{prefix}{n}"
            # "Điều" alone: group may not match; handle below
            if level in {"Article", "Clause"} and not raw.isdigit():
                return None

    # 2) Any arabic digits in title (Điều 12, …)
    m = _NUM_RE.search(title)
    if m:
        return f"{prefix}{int(m.group(1))}"

    # 3) Longest roman numeral anywhere in title (Chương-style)
    if level in {"Part", "Chapter", "Section", "SubSection"}:
        for roman, val in _ROMAN_VALUES:
            if re.search(rf"\b{roman}\b", title, re.IGNORECASE):
                return f"{prefix}{val}"

    # 4) Unreliable — do NOT guess sibling index (causes D2 collisions with real Điều 2)
    return None


def _allocate_token(
    level: str,
    title: str,
    nid: str,
    sibling_index: int,
    used: set[str],
) -> str | None:
    """Resolve a unique token among siblings; None = skip this level (unknown)."""
    prefix = _LEVEL_PREFIX.get(level)
    if prefix is None and level != "Point":
        return None

    token = _segment_token(level, title, sibling_index)
    if token and token not in used:
        return token

    if level == "Point":
        # Never steal a free letter for junk titles (e.g. "Điểm khoan") — that
        # shifts later real Điểm e/g/… . Use id-based label instead.
        if token and token not in used:
            return token
        return _id_token("p", nid, sibling_index)

    if prefix is None:
        return None

    # Numbered levels: if parsed token collides, or title weak → id-based unique
    if token and token in used:
        return _id_token(prefix, nid, sibling_index)
    if token is None:
        # Appendix / Group still allow sibling fallback
        if level in {"Appendix", "Group"}:
            cand = f"{prefix}{sibling_index + 1}"
            if cand not in used:
                return cand
            return _id_token(prefix, nid, sibling_index)
        return _id_token(prefix, nid, sibling_index)

    return token


@dataclass
class MucLucNode:
    id: str
    title: str
    level: str
    path: str  # structural, without doc_id prefix
    parent_path: str | None
    is_leaf: bool
    children: list["MucLucNode"] = field(default_factory=list)


@dataclass
class MucLucIndex:
    nodes: list[MucLucNode]
    id_to_node: dict[str, MucLucNode]
    id_to_path: dict[str, str]
    cut_leaves: list[MucLucNode]  # Point leaves or Clause leaves without Point children
    appendix_roots: list[MucLucNode]


def _clean_title(title: str) -> str:
    text = unicodedata.normalize("NFC", title or "")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


def build_muc_luc_index(muc_luc: list[dict[str, Any]]) -> MucLucIndex:
    nodes: list[MucLucNode] = []
    id_to_node: dict[str, MucLucNode] = {}
    id_to_path: dict[str, str] = {}
    cut_leaves: list[MucLucNode] = []
    appendix_roots: list[MucLucNode] = []

    def walk(raw_nodes: list[dict[str, Any]], parent_path: str | None) -> list[MucLucNode]:
        built: list[MucLucNode] = []
        level_counts: dict[str, int] = {}
        used_tokens: set[str] = set()
        for raw in raw_nodes:
            level = str(raw.get("level") or "Other")
            title = _clean_title(str(raw.get("title") or ""))
            nid = str(raw.get("id") or raw.get("key") or "")
            idx = level_counts.get(level, 0)
            level_counts[level] = idx + 1
            token = _allocate_token(level, title, nid, idx, used_tokens)
            if token is None:
                # unknown level — still walk children under same parent
                walk(list(raw.get("children") or []), parent_path)
                continue
            used_tokens.add(token)
            path = f"{parent_path}.{token}" if parent_path else token
            children_raw = list(raw.get("children") or [])
            node = MucLucNode(
                id=nid,
                title=title,
                level=level,
                path=path,
                parent_path=parent_path,
                is_leaf=bool(raw.get("isLeaf")) or not children_raw,
            )
            node.children = walk(children_raw, path)
            if level == "Appendix":
                appendix_roots.append(node)
            nodes.append(node)
            if nid:
                id_to_node[nid] = node
                id_to_path[nid] = path
            built.append(node)
        return built

    walk(muc_luc, None)

    for node in nodes:
        if node.level == "Point":
            cut_leaves.append(node)
        elif node.level == "Clause" and not any(c.level == "Point" for c in node.children):
            cut_leaves.append(node)
        elif node.level == "Article" and node.is_leaf and not node.children:
            cut_leaves.append(node)
        elif node.level == "Group" and node.is_leaf:
            # appendix group leaf handled in appendix module; still index
            pass

    return MucLucIndex(
        nodes=nodes,
        id_to_node=id_to_node,
        id_to_path=id_to_path,
        cut_leaves=cut_leaves,
        appendix_roots=appendix_roots,
    )


def graph_nodes_for_doc(index: MucLucIndex, doc_id: str) -> list[dict[str, Any]]:
    """Neo4j nodes with path = ltree text `{sanitized_doc}.{structural}`."""
    out: list[dict[str, Any]] = []
    for n in index.nodes:
        path = to_ltree_path(doc_id, n.path)
        parent = to_ltree_path(doc_id, n.parent_path) if n.parent_path else None
        out.append(
            {
                "path": path,
                "level": n.level,
                "label": n.title,
                "parent_path": parent,
            }
        )
    return out


def prefixed_ref(doc_id: str, structural_path: str) -> str:
    return f"{doc_id}:{structural_path}"


def sanitize_doc_id_for_ltree(doc_id: str) -> str:
    """ltree labels: [A-Za-z0-9_]; map other chars to underscore."""
    return re.sub(r"[^A-Za-z0-9_]", "_", doc_id or "") or "doc"


def to_ltree_path(doc_id: str, structural_path: str | None) -> str | None:
    """Build ltree text `{sanitized_doc}.{structural}` from chunk structural path."""
    if not structural_path:
        return sanitize_doc_id_for_ltree(doc_id)
    struct = structural_path.strip().lstrip(".")
    if not struct:
        return sanitize_doc_id_for_ltree(doc_id)
    return f"{sanitize_doc_id_for_ltree(doc_id)}.{struct}"


def chunk_ref_to_ltree(chunk_ref: str) -> str | None:
    """`{doc_id}:{structural}` → ltree text."""
    if not chunk_ref or ":" not in chunk_ref:
        return None
    doc_id, structural = chunk_ref.split(":", 1)
    if not structural:
        return None
    return to_ltree_path(doc_id, structural)


def article_root_ltree(ltree_path: str | None) -> str | None:
    """Prefix through nearest D* label (Điều), else None."""
    if not ltree_path:
        return None
    parts = ltree_path.split(".")
    for i in range(len(parts) - 1, -1, -1):
        if re.fullmatch(r"D\d+", parts[i]):
            return ".".join(parts[: i + 1])
    return None


def graph_nodes_as_legal_nodes(
    index: MucLucIndex,
    doc_id: str,
    *,
    path_root: str | None = None,
) -> list[dict[str, Any]]:
    """Hierarchy node dicts for PG upsert (7 tables via LegalChunkRepository.upsert_nodes).

    ``path_root`` defaults to ``doc_id``; pass ``doc_num`` to align with
    ``legal_documents.path`` (e.g. ``100_2015_QH13.P1``).
    """
    root = path_root or doc_id
    doc_root = to_ltree_path(root, None)
    out: list[dict[str, Any]] = []
    for i, n in enumerate(index.nodes):
        parent = (
            to_ltree_path(root, n.parent_path)
            if n.parent_path
            else (doc_root if n.level == "Part" else None)
        )
        out.append(
            {
                "doc_id": doc_id,
                "level": n.level,
                "label": n.title,
                "path": to_ltree_path(root, n.path),
                "parent_path": parent,
                "sort_order": i,
                "muc_luc_id": n.id or None,
                "eff_from": None,
                "eff_to": None,
                "eff_flag": None,
                "status_flag": 0,
            }
        )
    return out
