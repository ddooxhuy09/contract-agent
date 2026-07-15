from typing import List
from app.core.config import TOP_K_RETRIEVAL, SIMILARITY_THRESHOLD
from langchain_core.documents import Document
from app.vectorstore.faiss_store import get_contract_collection, get_legal_collection


def retrieve_contract(query: str, contract_id: str, k: int = None) -> List[Document]:
    # No min_score threshold here: this search is already scoped to a single contract's own
    # chunks via `where`, so even a "weakly similar" top-k result is still guaranteed to be
    # that contract's own text. Applying the same strict threshold used for the shared legal
    # corpus caused broad questions (e.g. "hợp đồng này có vấn đề gì không?") to retrieve
    # nothing and trigger a false "no context" refusal.
    return get_contract_collection().similarity_search(
        query, k=k or TOP_K_RETRIEVAL, where={"contract_id": contract_id}
    )


def retrieve_legal(query: str, k: int = 3) -> List[Document]:
    return get_legal_collection().similarity_search(query, k=k, min_score=SIMILARITY_THRESHOLD)
