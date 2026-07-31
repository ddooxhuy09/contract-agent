"""Build structural paths and graph nodes from muc_luc.json."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

_LEVEL_PREFIX = {
    "Chapter": "C",
    "Section": "M",
    "Article": "D",
    "Clause": "K",
    "Appendix": "PL",
    "Group": "N",
}

_NUM_RE = re.compile(r"(\d+)", re.UNICODE)
_POINT_RE = re.compile(r"(?:Điểm|ĐIỂM)\s*([a-zA-ZđĐ])", re.UNICODE)
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}


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


def _point_letter(title: str, fallback_index: int) -> str:
    m = _POINT_RE.search(title)
    if not m:
        # a, b, ... for fallback
        return chr(ord("a") + fallback_index) if fallback_index < 26 else f"p{fallback_index + 1}"
    ch = m.group(1).lower()
    if ch == "đ":
        return "dd"
    return ch


def _segment_token(level: str, title: str, sibling_index: int) -> str | None:
    prefix = _LEVEL_PREFIX.get(level)
    if level == "Point":
        return _point_letter(title, sibling_index)
    if prefix is None:
        return None
    m = _NUM_RE.search(title)
    if m:
        return f"{prefix}{int(m.group(1))}"
    # Chương I / Mục I
    for roman, val in _ROMAN.items():
        if re.search(rf"\b{roman}\b", title, re.IGNORECASE):
            return f"{prefix}{val}"
    return f"{prefix}{sibling_index + 1}"


def build_muc_luc_index(muc_luc: list[dict[str, Any]]) -> MucLucIndex:
    nodes: list[MucLucNode] = []
    id_to_node: dict[str, MucLucNode] = {}
    id_to_path: dict[str, str] = {}
    cut_leaves: list[MucLucNode] = []
    appendix_roots: list[MucLucNode] = []

    def walk(raw_nodes: list[dict[str, Any]], parent_path: str | None) -> list[MucLucNode]:
        built: list[MucLucNode] = []
        # counters per level among siblings for fallback
        level_counts: dict[str, int] = {}
        for raw in raw_nodes:
            level = str(raw.get("level") or "Other")
            title = _clean_title(str(raw.get("title") or ""))
            nid = str(raw.get("id") or raw.get("key") or "")
            idx = level_counts.get(level, 0)
            level_counts[level] = idx + 1
            token = _segment_token(level, title, idx)
            if token is None:
                # skip unknown levels but still walk children under same parent
                walk(list(raw.get("children") or []), parent_path)
                continue
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
            # recompute leaf: clause with only points → not a cut leaf; points are
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
    """Neo4j nodes with path = `{doc_id}:{structural}` so Chunk.chunk_ref matches."""
    out: list[dict[str, Any]] = []
    for n in index.nodes:
        path = f"{doc_id}:{n.path}"
        parent = f"{doc_id}:{n.parent_path}" if n.parent_path else None
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
