"""Compatibility shim — prefer HuggingFaceEmbedder in infrastructure."""

from app.infrastructure.embeddings.hf_embedder import HuggingFaceEmbedder, _build_embeddings


def get_embeddings():
    return _build_embeddings()
