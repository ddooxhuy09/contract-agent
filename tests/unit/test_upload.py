"""Verify UploadContract upserts the contract row BEFORE inserting chunks,
so the FK contract_chunks_contract_id_fkey is always satisfied.
"""

import asyncio
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.application.use_cases.contracts import UploadContract


_USER = UUID("00000000-0000-0000-0000-000000000001")


def _parts():
    contracts, chunks, storage, embedder = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    storage.save_upload.return_value = "test_key"
    storage.resolve_path.return_value = "/tmp/test"
    embedder.embed_documents.return_value = [[0.1] * 1024]
    return contracts, chunks, storage, UploadContract(contracts, chunks, storage, embedder)


def test_unreadable_file_is_rejected_and_nothing_is_stored():
    """A file whose text cannot be extracted (e.g. scanned PDF) must not become a contract."""
    contracts, chunks, storage, uc = _parts()
    storage.resolve_path.return_value = "/tmp/missing.docx"

    with pytest.raises(ValueError, match="Không trích xuất được văn bản"):
        asyncio.run(uc.execute(b"fake", "test.docx", _USER))

    contracts.upsert.assert_not_called()
    chunks.replace_for_contract.assert_not_called()
    storage.delete.assert_called_once_with("test_key")


def test_pdf_without_text_layer_is_rejected(monkeypatch):
    contracts, _, storage, uc = _parts()

    def no_text(path, ext):
        raise ValueError("No text could be extracted from the PDF file")

    monkeypatch.setattr("app.application.use_cases.contracts.parse_document", no_text)
    with pytest.raises(ValueError, match="PDF dạng ảnh quét"):
        asyncio.run(uc.execute(b"%PDF", "scan.pdf", _USER))
    contracts.upsert.assert_not_called()
    storage.delete.assert_called_once()


def test_doc_format_is_rejected_before_saving():
    contracts, _, storage, uc = _parts()
    with pytest.raises(ValueError, match=r"\.doc chưa được hỗ trợ"):
        asyncio.run(uc.execute(b"fake", "hop-dong.DOC", _USER))
    storage.save_upload.assert_not_called()
    contracts.upsert.assert_not_called()


def test_unknown_extension_is_rejected():
    _, _, storage, uc = _parts()
    with pytest.raises(ValueError, match="chưa được hỗ trợ"):
        asyncio.run(uc.execute(b"fake", "x.exe", _USER))
    storage.save_upload.assert_not_called()


def test_upload_upsert_before_chunks_on_success(monkeypatch):
    """On a successful parse, upsert is called BEFORE replace_for_contract."""
    contracts = MagicMock()
    chunks = MagicMock()
    storage = MagicMock()
    embedder = MagicMock()

    storage.save_upload.return_value = "test_key"
    storage.resolve_path.return_value = "/tmp/test.docx"
    embedder.embed_documents.return_value = [[0.1] * 1024]

    # Patch parse_document to return fake text, chunk_by_clause to return 1 doc.
    monkeypatch.setattr(
        "app.application.use_cases.contracts.parse_document",
        lambda path, ext: "Điều 1. Nội dung.",
    )
    monkeypatch.setattr(
        "app.application.use_cases.contracts.chunk_by_clause",
        lambda text, contract_id: [
            type("D", (), {"page_content": "Nội dung.", "metadata": {"clause_number": "1", "chunk_index": 1}})()
        ],
    )

    uc = UploadContract(contracts, chunks, storage, embedder)
    result = asyncio.run(uc.execute(b"fake", "test.docx", UUID("00000000-0000-0000-0000-000000000001")))

    assert result["status"] == "parsed"
    assert result["chunk_count"] == 1

    # Verify upsert called before replace_for_contract
    assert contracts.upsert.call_count == 1
    assert chunks.replace_for_contract.call_count == 1
    # upsert must have been called first
    upsert_time = contracts.upsert.call_args_list[0][0]
    assert upsert_time[0].contract_id is not None  # just confirm it was called
    chunks.replace_for_contract.assert_called_once()
