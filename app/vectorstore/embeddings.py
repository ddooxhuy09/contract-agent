import torch
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import EMBEDDING_MODEL, EMBEDDING_DEVICE, logger

_embeddings: HuggingFaceEmbeddings | None = None


def _resolve_device() -> str:
    if EMBEDDING_DEVICE != "auto":
        return EMBEDDING_DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        device = _resolve_device()
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL} on device={device}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": device, "trust_remote_code": True},
            encode_kwargs={"normalize_embeddings": True},
        )
        # BGE-m3 supports up to 8192 tokens, but our chunks are Dieu/Khoan/Diem-sized
        # (a few hundred tokens at most) - capping at 512 keeps CPU embedding fast without
        # truncating any real chunk. Not exposed as a constructor kwarg by
        # HuggingFaceEmbeddings, so set it on the underlying model directly.
        _embeddings._client.max_seq_length = 512
    return _embeddings
