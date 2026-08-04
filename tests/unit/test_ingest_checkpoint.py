"""Checkpoint resume for legal corpus batch ingest."""

from pathlib import Path

from app.infrastructure.legal_corpus.checkpoint import (
    checkpoint_path_for,
    completed_doc_ids,
    load_checkpoint,
    mark_completed,
    peek_doc_id,
    reset_checkpoint,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "legal_sample"


def test_mark_and_load_checkpoint(tmp_path: Path):
    ck = tmp_path / ".legal_ingest_checkpoint.json"
    mark_completed(ck, doc_id="a", folder=tmp_path / "a", chunk_count=10)
    mark_completed(ck, doc_id="b", folder=tmp_path / "b", chunk_count=20)
    data = load_checkpoint(ck)
    assert completed_doc_ids(data) == {"a", "b"}
    # Update same doc_id replaces, does not duplicate
    mark_completed(ck, doc_id="a", folder=tmp_path / "a", chunk_count=11)
    assert len(load_checkpoint(ck)["completed"]) == 2
    assert next(r for r in load_checkpoint(ck)["completed"] if r["doc_id"] == "a")["chunk_count"] == 11


def test_reset_checkpoint(tmp_path: Path):
    ck = checkpoint_path_for(tmp_path)
    mark_completed(ck, doc_id="x", folder=tmp_path, chunk_count=1)
    assert ck.is_file()
    reset_checkpoint(ck)
    assert not ck.is_file()
    assert completed_doc_ids(load_checkpoint(ck)) == set()


def test_peek_doc_id_fixture():
    assert peek_doc_id(FIXTURE) == "fixture-168"
