"""Assemble crawler folder → IngestLegalDocument artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.infrastructure.legal_corpus.appendix import appendix_graph_nodes, build_appendix_chunks
from app.infrastructure.legal_corpus.internal_refs import extract_path_relations
from app.infrastructure.legal_corpus.luoc_do_flatten import flatten_luoc_do
from app.infrastructure.legal_corpus.muc_luc_paths import (
    build_muc_luc_index,
    chunk_ref_to_ltree,
    graph_nodes_as_legal_nodes,
    graph_nodes_for_doc,
    to_ltree_path,
)
from app.infrastructure.legal_corpus.thuoc_tinh_mapper import map_thuoc_tinh
from app.infrastructure.legal_corpus.van_ban_chunker import build_body_chunks, meta_graph_nodes


def _meta_legal_nodes(doc_id: str, paths: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        if not path:
            continue
        leaf = path.rsplit(".", 1)[-1]
        if leaf == "PREAMBLE":
            out.append(
                {
                    "doc_id": doc_id,
                    "level": "Meta",
                    "label": "PREAMBLE",
                    "path": path,
                    "parent_path": to_ltree_path(doc_id, None),
                    "sort_order": -2,
                    "muc_luc_id": None,
                    "eff_from": None,
                    "eff_to": None,
                    "eff_flag": None,
                    "status_flag": 0,
                }
            )
        elif leaf == "SIGN":
            out.append(
                {
                    "doc_id": doc_id,
                    "level": "Meta",
                    "label": "SIGN",
                    "path": path,
                    "parent_path": to_ltree_path(doc_id, None),
                    "sort_order": 99999,
                    "muc_luc_id": None,
                    "eff_from": None,
                    "eff_to": None,
                    "eff_flag": None,
                    "status_flag": 0,
                }
            )
    return out


def load_document_folder(folder: Path | str) -> dict[str, Any]:
    """Load one crawler document folder into ingest-ready dict.

    Returns:
        {
          thuoc_tinh, chunks, relations, graph_nodes, legal_nodes, stub_docs, folder
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
    # Hierarchy / Neo4j tree rooted by số hiệu when available (matches legal_documents.path)
    path_root = str(thuoc_tinh.get("doc_num") or doc_id)

    index = build_muc_luc_index(muc_luc)
    body_chunks = build_body_chunks(van_ban, index, doc_id)
    appendix_chunks = build_appendix_chunks(van_ban, index, doc_id)
    chunks = body_chunks + appendix_chunks
    for c in chunks:
        if not c.get("path") and c.get("chunk_ref"):
            c["path"] = chunk_ref_to_ltree(c["chunk_ref"])

    # Same-doc Điều/Khoản/Điểm/Chương citations → path relations (root = chunk root)
    path_relations = extract_path_relations(chunks, index)

    relations, stub_docs = flatten_luoc_do(luoc_do_raw)

    graph_nodes = graph_nodes_for_doc(index, path_root)
    graph_nodes.extend(meta_graph_nodes(doc_id, [c["path"] for c in chunks if c.get("path")]))
    # Appendix nodes that may not be fully in muc_luc
    existing = {n["path"] for n in graph_nodes}
    for n in appendix_graph_nodes(appendix_chunks, doc_id):
        if n["path"] not in existing:
            graph_nodes.append(n)
            existing.add(n["path"])

    legal_nodes = graph_nodes_as_legal_nodes(index, doc_id, path_root=path_root)
    legal_nodes.extend(_meta_legal_nodes(doc_id, [c["path"] for c in chunks if c.get("path")]))
    # Appendix structural nodes from graph_nodes (already ltree)
    seen_ltree = {n["path"] for n in legal_nodes}
    for gn in graph_nodes:
        lt = gn.get("path") or ""
        if ":" in lt:
            lt = chunk_ref_to_ltree(lt) or ""
        if not lt or lt in seen_ltree:
            continue
        parent = gn.get("parent_path")
        if parent and ":" in parent:
            parent = chunk_ref_to_ltree(parent)
        legal_nodes.append(
            {
                "doc_id": doc_id,
                "level": gn.get("level") or "Appendix",
                "label": gn.get("label"),
                "path": lt,
                "parent_path": parent,
                "sort_order": None,
                "muc_luc_id": None,
                "eff_from": None,
                "eff_to": None,
                "eff_flag": None,
                "status_flag": 0,
            }
        )
        seen_ltree.add(lt)

    return {
        "thuoc_tinh": thuoc_tinh,
        "chunks": chunks,
        "relations": relations,
        "path_relations": path_relations,
        "graph_nodes": graph_nodes,
        "legal_nodes": legal_nodes,
        "stub_docs": stub_docs,
        "folder": str(folder),
    }
