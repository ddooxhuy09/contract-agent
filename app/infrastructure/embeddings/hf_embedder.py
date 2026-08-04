from functools import lru_cache
from threading import Lock

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.logging import logger
from app.core.settings import get_settings

_load_lock = Lock()


@lru_cache
def _build_embeddings() -> HuggingFaceEmbeddings:
    settings = get_settings()
    device = settings.embedding_device
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

    logger.info(
        "Loading embeddings model=%s dim=%s device=%s max_seq_length=%s",
        settings.embedding_model,
        settings.embedding_dim,
        device,
        settings.embedding_max_seq_length,
    )
    emb = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={
            "device": device,
            "trust_remote_code": settings.embedding_trust_remote_code,
        },
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )
    # HuggingFaceEmbeddings does not expose max_seq_length as a constructor kwarg.
    client = getattr(emb, "_client", None)
    if client is not None and hasattr(client, "max_seq_length"):
        client.max_seq_length = settings.embedding_max_seq_length
    return emb


def _get_embeddings() -> HuggingFaceEmbeddings:
    # lru_cache alone races on first concurrent calls — serialize the initial load.
    with _load_lock:
        return _build_embeddings()


class HuggingFaceEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _get_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return _get_embeddings().embed_query(text)
