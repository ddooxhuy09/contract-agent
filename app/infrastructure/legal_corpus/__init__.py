"""Crawler-folder → ingest artifacts (thuoc_tinh / muc_luc / van_ban / luoc_do)."""

from app.infrastructure.legal_corpus.assemble import load_document_folder
from app.infrastructure.legal_corpus.discover import discover_document_folders

__all__ = ["discover_document_folders", "load_document_folder"]
