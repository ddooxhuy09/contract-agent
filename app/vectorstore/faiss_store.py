import os
import shutil
import threading

from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document

from app.core.config import VECTOR_STORE_DIR, logger
from app.vectorstore.embeddings import get_embeddings


class FaissStore:
    """Thin wrapper around LangChain's FAISS vectorstore with per-contract metadata
    filtering, persisted to disk. LangChain FAISS can't be constructed empty, so the
    underlying store is created lazily on the first `add_documents` call.
    """

    def __init__(self, name: str):
        self.name = name
        self.folder_path = os.path.join(VECTOR_STORE_DIR, name)
        self._lock = threading.Lock()
        self._store: FAISS | None = self._load()

    def _load(self) -> FAISS | None:
        if os.path.isdir(self.folder_path):
            try:
                return FAISS.load_local(
                    self.folder_path, get_embeddings(), allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.error(f"Failed to load FAISS store '{self.name}': {e}, starting fresh")
        return None

    def save(self):
        with self._lock:
            if self._store is not None:
                self._store.save_local(self.folder_path)

    def reset(self):
        """Wipe the collection in memory and on disk (used to rebuild from a source of truth)."""
        with self._lock:
            self._store = None
            if os.path.isdir(self.folder_path):
                shutil.rmtree(self.folder_path)

    def add_documents(self, docs: list[Document], persist: bool = True):
        if not docs:
            return
        with self._lock:
            if self._store is None:
                # MAX_INNER_PRODUCT + normalized embeddings (see embeddings.py) reproduces
                # cosine similarity, matching the FaissStore this replaced (faiss.IndexFlatIP).
                self._store = FAISS.from_documents(
                    docs, get_embeddings(), distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT
                )
            else:
                self._store.add_documents(docs)
        if persist:
            self.save()

    def get(self, where: dict | None = None) -> dict:
        if self._store is None:
            return {"documents": [], "metadatas": []}
        all_docs = list(self._store.docstore._dict.values())
        if where:
            all_docs = [d for d in all_docs if all(d.metadata.get(k) == v for k, v in where.items())]
        return {
            "documents": [d.page_content for d in all_docs],
            "metadatas": [d.metadata for d in all_docs],
        }

    def similarity_search(self, query: str, k: int = 5, where: dict | None = None, min_score: float | None = None) -> list[Document]:
        if self._store is None:
            return []
        kwargs = {"score_threshold": min_score} if min_score is not None else {}
        return self._store.similarity_search(query, k=k, filter=where, **kwargs)


_contract_collection = None
_legal_collection = None


def get_contract_collection() -> FaissStore:
    global _contract_collection
    if _contract_collection is None:
        _contract_collection = FaissStore("contracts")
    return _contract_collection


def get_legal_collection() -> FaissStore:
    global _legal_collection
    if _legal_collection is None:
        _legal_collection = FaissStore("legal")
    return _legal_collection
