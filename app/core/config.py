"""Backward-compatible settings facade for legacy modules. """
from app.core.logging import logger
from app.core.settings import get_settings

_settings = get_settings()

GEMINI_API_KEY = _settings.gemini_api_key
GEMINI_MODEL = _settings.gemini_model
EMBEDDING_MODEL = _settings.embedding_model
EMBEDDING_DEVICE = _settings.embedding_device
DATABASE_URL = _settings.database_url
UPLOAD_DIR = str(_settings.upload_path)
MAX_CHUNK_SIZE = _settings.max_chunk_size
CHUNK_OVERLAP = _settings.chunk_overlap
TOP_K_RETRIEVAL = _settings.top_k_retrieval
SIMILARITY_THRESHOLD = _settings.similarity_threshold
VECTOR_STORE_DIR = "data/vector_store"  # deprecated (FAISS removed)
LEGAL_KB_BATCH_SIZE = 256
LEGAL_KB_ACTIVE_ONLY = True

__all__ = [
    "logger",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DEVICE",
    "DATABASE_URL",
    "UPLOAD_DIR",
    "MAX_CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "TOP_K_RETRIEVAL",
    "SIMILARITY_THRESHOLD",
    "VECTOR_STORE_DIR",
    "LEGAL_KB_BATCH_SIZE",
    "LEGAL_KB_ACTIVE_ONLY",
]
