"""Appendix chunking: always include title + table header row with each data row."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.infrastructure.legal_corpus.muc_luc_paths import MucLucIndex, MucLucNode, prefixed_ref

_PL_HEADING = re.compile(
    r"^(?:#{1,3}\s*)?\**\s*(Phụ\s*lục|PHỤ\s*LỤC)\s*([A-Z0-9IVX]+)?\s*\**\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_MD_ROW = re.compile(r"^\|(.+)\|$", re.MULTILINE)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return True
    return all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells)


def _parse_md_tables(block: str) -> list[tuple[str, list[str]]]:
    """Return list of (header_line, data_row_lines) for markdown tables in block."""
    lines = block.splitlines()
    tables: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("|"):
            i += 1
            continue
        rows: list[str] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append(lines[i].strip())
            i += 1
        if len(rows) < 2:
            continue
        header = rows[0]
        # skip separator
        data_start = 1
        cells = [c.strip() for c in header.strip("|").split("|")]
        if data_start < len(rows):
            sep_cells = [c.strip() for c in rows[1].strip("|").split("|")]
            if _is_separator_row(sep_cells):
                data_start = 2
        data_rows = rows[data_start:]
        if data_rows:
            tables.append((header, data_rows))
    return tables


def build_appendix_chunks(
    van_ban: str,
    index: MucLucIndex,
    doc_id: str,
) -> list[dict[str, Any]]:
    """Build appendix chunks from muc_luc Appendix nodes and/or Phụ lục headings in van_ban."""
    text = _nfc(van_ban)
    chunks: list[dict[str, Any]] = []

    if index.appendix_roots:
        for pl_i, root in enumerate(index.appendix_roots):
            chunks.extend(_chunks_for_appendix_node(root, text, doc_id, pl_i))
        return chunks

    # Fallback: scan van_ban for Phụ lục headings even if muc_luc omitted them
    matches = list(_PL_HEADING.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        title_line = m.group(0).strip().strip("*").strip()
        pl_token = f"PL{i}"
        structural = pl_token
        tables = _parse_md_tables(block)
        if not tables:
            chunks.append(
                {
                    "chunk_ref": prefixed_ref(doc_id, structural),
                    "chunk_type": "appendix",
                    "chunk_text": block[:8000],
                    "is_effective": True,
                }
            )
            continue
        for t_i, (header, data_rows) in enumerate(tables):
            for r_i, row in enumerate(data_rows, start=1):
                path = f"{structural}.N{t_i + 1}.R{r_i}"
                body = f"{title_line}\n{header}\n{row}"
                chunks.append(
                    {
                        "chunk_ref": prefixed_ref(doc_id, path),
                        "chunk_type": "appendix",
                        "chunk_text": body,
                        "is_effective": True,
                    }
                )
    return chunks


def _chunks_for_appendix_node(
    root: MucLucNode,
    van_ban: str,
    doc_id: str,
    pl_index: int,
) -> list[dict[str, Any]]:
    title = root.title
    # Locate block by title proximity
    pattern = re.compile(re.escape(title), re.IGNORECASE)
    m = pattern.search(van_ban)
    if m:
        # take until next Phụ lục or EOF
        rest = van_ban[m.start() :]
        nxt = _PL_HEADING.search(rest, 1)
        block = rest[: nxt.start()] if nxt else rest
    else:
        block = title

    chunks: list[dict[str, Any]] = []
    groups = [c for c in root.children if c.level == "Group"] or [root]
    tables = _parse_md_tables(block)

    if tables:
        header, data_rows = tables[0]
        for r_i, row in enumerate(data_rows, start=1):
            # Prefer muc_luc group path when available
            if groups and groups[0] is not root and r_i <= len(groups):
                path = groups[r_i - 1].path
            else:
                path = f"{root.path}.N1.R{r_i}"
            chunks.append(
                {
                    "chunk_ref": prefixed_ref(doc_id, path),
                    "chunk_type": "appendix",
                    "chunk_text": f"{title}\n{header}\n{row}",
                    "is_effective": True,
                }
            )
        return chunks

    # No table: one chunk per group leaf, always prefix title
    if groups and groups[0] is not root:
        for g in groups:
            chunks.append(
                {
                    "chunk_ref": prefixed_ref(doc_id, g.path),
                    "chunk_type": "appendix",
                    "chunk_text": f"{title}\n{g.title}",
                    "is_effective": True,
                }
            )
    else:
        chunks.append(
            {
                "chunk_ref": prefixed_ref(doc_id, root.path),
                "chunk_type": "appendix",
                "chunk_text": block[:8000] if block else title,
                "is_effective": True,
            }
        )
    return chunks


def appendix_graph_nodes(chunks: list[dict[str, Any]], doc_id: str) -> list[dict[str, Any]]:
    """Ensure Neo4j nodes exist for appendix chunk_refs not already in muc_luc."""
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ch in chunks:
        ref = ch["chunk_ref"]
        if not ref.startswith(f"{doc_id}:"):
            continue
        structural = ref[len(doc_id) + 1 :]
        parts = structural.split(".")
        for i in range(len(parts)):
            path = f"{doc_id}:{'.'.join(parts[: i + 1])}"
            if path in seen:
                continue
            seen.add(path)
            seg = parts[i]
            if seg.startswith("PL"):
                level = "Appendix"
            elif seg.startswith("N"):
                level = "Group"
            elif seg.startswith("R"):
                level = "Group"
            else:
                level = "Group"
            parent = f"{doc_id}:{'.'.join(parts[:i])}" if i else None
            nodes.append(
                {
                    "path": path,
                    "level": level,
                    "label": seg,
                    "parent_path": parent,
                }
            )
    return nodes
