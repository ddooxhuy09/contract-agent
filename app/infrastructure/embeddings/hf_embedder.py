from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.logging import logger
from app.core.settings import get_settings


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
    logger.info("Loading embeddings model=%s device=%s", settings.embedding_model, device)
    emb = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )
    client = getattr(emb, "_client", None)
    if client is not None and hasattr(client, "max_seq_length"):
        client.max_seq_length = 256
    return emb


class HuggingFaceEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _build_embeddings().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return _build_embeddings().embed_query(text)
