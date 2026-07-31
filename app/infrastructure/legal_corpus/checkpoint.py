"""Persist completed legal-doc ingest ids so batch runs can resume without overwrite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CHECKPOINT_NAME = ".legal_ingest_checkpoint.json"


def checkpoint_path_for(root: Path) -> Path:
    root = root.resolve()
    if root.is_file():
        root = root.parent
    return root / CHECKPOINT_NAME


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": 1, "completed": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "completed": []}
    if not isinstance(data, dict):
        return {"version": 1, "completed": []}
    data.setdefault("version", 1)
    data.setdefault("completed", [])
    if not isinstance(data["completed"], list):
        data["completed"] = []
    return data


def completed_doc_ids(checkpoint: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for row in checkpoint.get("completed") or []:
        if isinstance(row, dict) and row.get("doc_id"):
            ids.add(str(row["doc_id"]))
        elif isinstance(row, str):
            ids.add(row)
    return ids


def mark_completed(
    path: Path,
    *,
    doc_id: str,
    folder: str | Path,
    chunk_count: int,
    relation_count: int = 0,
) -> None:
    data = load_checkpoint(path)
    completed = data.setdefault("completed", [])
    # Replace existing entry for same doc_id if any
    completed = [r for r in completed if not (isinstance(r, dict) and str(r.get("doc_id")) == doc_id)]
    completed.append(
        {
            "doc_id": doc_id,
            "folder": str(folder),
            "chunk_count": chunk_count,
            "relation_count": relation_count,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    data["completed"] = completed
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def peek_doc_id(folder: Path) -> str:
    raw = json.loads((folder / "thuoc_tinh.json").read_text(encoding="utf-8"))
    return str(raw["doc_id"])


def reset_checkpoint(path: Path) -> None:
    if path.is_file():
        path.unlink()
