"""Cut van_ban.md into body chunks guided by muc_luc (Điều / Khoản / Điểm)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.infrastructure.legal_corpus.effectivity import is_effectivity_title
from app.infrastructure.legal_corpus.muc_luc_paths import MucLucIndex, MucLucNode, to_ltree_path

# IDs are usually UUID hex; allow alphanumeric for fixtures / alternate crawlers.
_ARTICLE_ANCHOR = re.compile(
    r"<!--\s*article_id:\s*([0-9a-zA-Z_-]+)\s*-->",
)
_CLAUSE_ANCHOR = re.compile(
    r"<!--\s*clause_id:\s*([0-9a-zA-Z_-]+)\s*-->",
)
_ARTICLE_HEADING = re.compile(
    r"^#{1,3}\s*\**\s*(Điều\s+\d+[^\n]*?)\**\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_POINT_SPLIT = re.compile(
    r"(?m)^(?:\*?([a-zđ])\)\*?\s+)",
    re.IGNORECASE,
)
_SIGN_HINT = re.compile(
    r"(nơi\s*nhận|kt\.\s*thủ\s*tướng|tm\.\s*chính\s*phủ|ký\s*tên)",
    re.IGNORECASE,
)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").replace("\u00a0", " ")


@dataclass
class _Span:
    id: str
    start: int  # position of content start (after anchor / marker)
    end: int
    kind: str  # article | clause


def _line_start(text: str, pos: int) -> int:
    """Start of the line containing ``pos`` (crawler puts lead text before <!-- clause_id -->)."""
    nl = text.rfind("\n", 0, pos)
    return 0 if nl < 0 else nl + 1


def _build_spans(text: str) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    """Map article_id / clause_id → (start, end) content ranges in van_ban."""
    # (sort_key, content_start, kind, id)
    markers: list[tuple[int, int, str, str]] = []
    for m in _ARTICLE_ANCHOR.finditer(text):
        # Article body usually starts after the comment; heading is resolved separately.
        markers.append((m.start(), m.end(), "article", m.group(1)))
    for m in _CLAUSE_ANCHOR.finditer(text):
        # Include "1. …" lead that sits on the same line before the HTML comment.
        content_start = _line_start(text, m.start())
        markers.append((m.start(), content_start, "clause", m.group(1)))
    markers.sort(key=lambda x: x[0])

    articles: dict[str, tuple[int, int]] = {}
    clauses: dict[str, tuple[int, int]] = {}
    for i, (_sort, content_start, kind, nid) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        if kind == "article":
            articles[nid] = (content_start, end)
        else:
            # Strip the HTML comment from the clause span when slicing later
            clauses[nid] = (content_start, end)
    return articles, clauses


def _article_rubric(text: str, article_id: str | None, article_span: tuple[int, int] | None) -> str:
    if article_span:
        # Look backward from span start for heading
        window_start = max(0, article_span[0] - 400)
        window = text[window_start : article_span[0] + 80]
        headings = list(_ARTICLE_HEADING.finditer(window))
        if headings:
            return _nfc(headings[-1].group(1)).strip().strip("*").strip()
    if article_id:
        # search whole doc for anchor then heading before it
        m = re.search(
            rf"<!--\s*article_id:\s*{re.escape(article_id)}\s*-->",
            text,
        )
        if m:
            window = text[max(0, m.start() - 400) : m.start()]
            headings = list(_ARTICLE_HEADING.finditer(window))
            if headings:
                return _nfc(headings[-1].group(1)).strip().strip("*").strip()
    return ""


def _split_points(clause_body: str) -> list[tuple[str, str]]:
    """Return [(letter, point_text including marker), ...] in order."""
    body = clause_body.strip()
    if not body:
        return []
    matches = list(_POINT_SPLIT.finditer(body))
    if not matches:
        return []
    points: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        letter = m.group(1).lower()
        if letter == "đ":
            letter = "dd"
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        points.append((letter, body[start:end].strip()))
    return points


def _clause_lead_and_points(clause_body: str) -> tuple[str, list[tuple[str, str]]]:
    points = _split_points(clause_body)
    if not points:
        return clause_body.strip(), []
    first_pos = clause_body.find(points[0][1][:20]) if points[0][1] else -1
    # lead = text before first point marker
    m0 = _POINT_SPLIT.search(clause_body)
    lead = clause_body[: m0.start()].strip() if m0 else ""
    return lead, points


def _path_index(index: MucLucIndex) -> dict[str, MucLucNode]:
    return {n.path: n for n in index.nodes}


def _find_ancestor(index: MucLucIndex, node: MucLucNode, level: str) -> MucLucNode | None:
    by_path = _path_index(index)
    path = node.parent_path
    while path:
        n = by_path.get(path)
        if n is None:
            return None
        if n.level == level:
            return n
        path = n.parent_path
    return None


def _parent_article(index: MucLucIndex, node: MucLucNode) -> MucLucNode | None:
    if node.level == "Article":
        return node
    return _find_ancestor(index, node, "Article")


def _parent_clause(index: MucLucIndex, node: MucLucNode) -> MucLucNode | None:
    if node.level == "Clause":
        return node
    return _find_ancestor(index, node, "Clause")


def build_body_chunks(
    van_ban: str,
    index: MucLucIndex,
    doc_id: str,
) -> list[dict[str, Any]]:
    text = _nfc(van_ban)
    articles, clauses = _build_spans(text)
    chunks: list[dict[str, Any]] = []

    # Preamble: before first article heading / first article anchor
    first_article_pos = len(text)
    m_head = _ARTICLE_HEADING.search(text)
    if m_head:
        first_article_pos = min(first_article_pos, m_head.start())
    m_anch = _ARTICLE_ANCHOR.search(text)
    if m_anch:
        # include heading before anchor
        first_article_pos = min(first_article_pos, m_anch.start())
    preamble = text[:first_article_pos].strip()
    if preamble and len(preamble) > 40:
        chunks.append(
            {
                "path": to_ltree_path(doc_id, "PREAMBLE"),
                "chunk_type": "preamble",
                "chunk_text": preamble[:12000],
                "is_effective": True,
            }
        )

    for leaf in index.cut_leaves:
        if leaf.level == "Point":
            chunk = _chunk_for_point(leaf, index, text, articles, clauses, doc_id)
        elif leaf.level == "Clause":
            chunk = _chunk_for_clause_leaf(leaf, index, text, articles, clauses, doc_id)
        else:
            chunk = _chunk_for_article_leaf(leaf, index, text, articles, doc_id)
        if chunk:
            chunks.append(chunk)

    # Signature: trailing block after last article content if it looks like signature
    if index.cut_leaves:
        last_ends = []
        for leaf in index.cut_leaves:
            art = _parent_article(index, leaf)
            if art and art.id in articles:
                last_ends.append(articles[art.id][1])
            cl = _parent_clause(index, leaf) if leaf.level != "Article" else None
            if cl and cl.id in clauses:
                last_ends.append(clauses[cl.id][1])
        if last_ends:
            tail = text[max(last_ends) :].strip()
            if tail and _SIGN_HINT.search(tail) and len(tail) > 20:
                chunks.append(
                    {
                        "path": to_ltree_path(doc_id, "SIGN"),
                        "chunk_type": "signature",
                        "chunk_text": tail[:8000],
                        "is_effective": True,
                    }
                )

    return chunks


def _chunk_for_point(
    leaf: MucLucNode,
    index: MucLucIndex,
    text: str,
    articles: dict[str, tuple[int, int]],
    clauses: dict[str, tuple[int, int]],
    doc_id: str,
) -> dict[str, Any] | None:
    clause = _parent_clause(index, leaf)
    article = _parent_article(index, leaf)
    rubric = ""
    if article:
        rubric = _article_rubric(text, article.id, articles.get(article.id))
        if not rubric:
            rubric = article.title
    else:
        rubric = "Điều ?"

    clause_body = ""
    if clause and clause.id in clauses:
        s, e = clauses[clause.id]
        clause_body = text[s:e]
        # strip nested anchors noise (keep surrounding text)
        clause_body = _CLAUSE_ANCHOR.sub("", clause_body)
        clause_body = _ARTICLE_ANCHOR.sub("", clause_body)
        clause_body = re.sub(r"[ \t]+\n", "\n", clause_body)
    lead, points = _clause_lead_and_points(clause_body)

    # Match point letter from path suffix
    letter = leaf.path.rsplit(".", 1)[-1]
    point_text = ""
    for lit, body in points:
        if lit == letter or (letter == "dd" and lit in ("dd", "đ")):
            point_text = body
            break
    if not point_text:
        # fallback by sibling order among Point children
        if clause:
            siblings = [c for c in clause.children if c.level == "Point"]
            try:
                idx = siblings.index(leaf)
                if idx < len(points):
                    point_text = points[idx][1]
            except ValueError:
                pass
    if not point_text:
        point_text = leaf.title

    parts = [rubric]
    if lead:
        parts.append(lead)
    parts.append(point_text)
    chunk_text = "\n".join(parts).strip()

    chunk_type = "effectivity" if is_effectivity_title(rubric) else "body"

    return {
        "path": to_ltree_path(doc_id, leaf.path),
        "source_element_id": clause.id if clause else (article.id if article else None),
        "chunk_type": chunk_type,
        "chunk_text": chunk_text,
        "is_effective": True,
    }


def _chunk_for_clause_leaf(
    leaf: MucLucNode,
    index: MucLucIndex,
    text: str,
    articles: dict[str, tuple[int, int]],
    clauses: dict[str, tuple[int, int]],
    doc_id: str,
) -> dict[str, Any] | None:
    article = _parent_article(index, leaf)
    rubric = ""
    if article:
        rubric = _article_rubric(text, article.id, articles.get(article.id)) or article.title
    clause_body = ""
    if leaf.id in clauses:
        s, e = clauses[leaf.id]
        clause_body = text[s:e]
        clause_body = _CLAUSE_ANCHOR.sub("", clause_body).strip()
    else:
        clause_body = leaf.title

    chunk_text = f"{rubric}\n{clause_body}".strip()
    chunk_type = "effectivity" if is_effectivity_title(rubric) else "body"
    return {
        "path": to_ltree_path(doc_id, leaf.path),
        "source_element_id": leaf.id or (article.id if article else None),
        "chunk_type": chunk_type,
        "chunk_text": chunk_text,
        "is_effective": True,
    }


def _chunk_for_article_leaf(
    leaf: MucLucNode,
    index: MucLucIndex,
    text: str,
    articles: dict[str, tuple[int, int]],
    doc_id: str,
) -> dict[str, Any] | None:
    rubric = _article_rubric(text, leaf.id, articles.get(leaf.id)) or leaf.title
    body = ""
    if leaf.id in articles:
        s, e = articles[leaf.id]
        body = text[s:e]
        body = _ARTICLE_ANCHOR.sub("", body)
        body = _CLAUSE_ANCHOR.sub("", body).strip()
    chunk_text = f"{rubric}\n{body}".strip() if body else rubric
    chunk_type = "effectivity" if is_effectivity_title(rubric) else "body"
    return {
        "path": to_ltree_path(doc_id, leaf.path),
        "source_element_id": leaf.id or None,
        "chunk_type": chunk_type,
        "chunk_text": chunk_text,
        "is_effective": True,
    }


def meta_graph_nodes(doc_id: str, paths: list[str]) -> list[dict[str, Any]]:
    nodes = []
    for path in paths:
        leaf = (path or "").rsplit(".", 1)[-1]
        if leaf == "PREAMBLE":
            nodes.append(
                {
                    "path": path,
                    "level": "Meta",
                    "label": "PREAMBLE",
                    "parent_path": None,
                }
            )
        elif leaf == "SIGN":
            nodes.append(
                {
                    "path": path,
                    "level": "Meta",
                    "label": "SIGN",
                    "parent_path": None,
                }
            )
        elif leaf == "EFF":
            nodes.append(
                {
                    "path": path,
                    "level": "Meta",
                    "label": "EFF",
                    "parent_path": None,
                }
            )
    return nodes
