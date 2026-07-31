"""Assemble crawler folder → IngestLegalDocument artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.infrastructure.legal_corpus.appendix import appendix_graph_nodes, build_appendix_chunks
from app.infrastructure.legal_corpus.luoc_do_flatten import flatten_luoc_do
from app.infrastructure.legal_corpus.muc_luc_paths import build_muc_luc_index, graph_nodes_for_doc
from app.infrastructure.legal_corpus.thuoc_tinh_mapper import map_thuoc_tinh
from app.infrastructure.legal_corpus.van_ban_chunker import build_body_chunks, meta_graph_nodes


def load_document_folder(folder: Path | str) -> dict[str, Any]:
    """Load one crawler document folder into ingest-ready dict.

    Returns:
        {
          thuoc_tinh, chunks, relations, graph_nodes, stub_docs, folder
        }
    """
    folder = Path(folder)
    thuoc_tinh_raw = json.loads((folder / "thuoc_tinh.json").read_text(encoding="utf-8"))
    muc_luc = json.loads((folder / "muc_luc.json").read_text(encoding="utf-8"))
    van_ban = (folder / "van_ban.md").read_text(encoding="utf-8")

    luoc_do_raw = None
    luoc_path = folder / "luoc_do.json"
    if luoc_path.is_file():
        luoc_do_raw = json.loads(luoc_path.read_text(encoding="utf-8"))

    thuoc_tinh = map_thuoc_tinh(thuoc_tinh_raw, full_text=van_ban)
    doc_id = str(thuoc_tinh["doc_id"])

    index = build_muc_luc_index(muc_luc)
    body_chunks = build_body_chunks(van_ban, index, doc_id)
    appendix_chunks = build_appendix_chunks(van_ban, index, doc_id)
    chunks = body_chunks + appendix_chunks

    relations, stub_docs = flatten_luoc_do(luoc_do_raw)

    graph_nodes = graph_nodes_for_doc(index, doc_id)
    graph_nodes.extend(meta_graph_nodes(doc_id, [c["chunk_ref"] for c in chunks]))
    # Appendix nodes that may not be fully in muc_luc
    existing = {n["path"] for n in graph_nodes}
    for n in appendix_graph_nodes(appendix_chunks, doc_id):
        if n["path"] not in existing:
            graph_nodes.append(n)
            existing.add(n["path"])

    return {
        "thuoc_tinh": thuoc_tinh,
        "chunks": chunks,
        "relations": relations,
        "graph_nodes": graph_nodes,
        "stub_docs": stub_docs,
        "folder": str(folder),
    }
