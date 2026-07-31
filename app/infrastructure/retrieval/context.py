"""Runtime holders so legacy agent modules can retrieve without circular imports."""

from app.domain.ports.repositories import ContractChunkRepository, LegalChunkRepository
from app.domain.ports.services import ContractVectorSearch, GraphRepository, LegalVectorSearch
from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag

_contract_search: ContractVectorSearch | None = None
_legal_search: LegalVectorSearch | None = None
_graph: GraphRepository | None = None
_legal_chunks: LegalChunkRepository | None = None
_contract_chunks: ContractChunkRepository | None = None
_graph_rag: LegalGraphRag | None = None


def bind_retrieval(
    contract_search: ContractVectorSearch,
    legal_search: LegalVectorSearch,
    graph: GraphRepository | None = None,
    legal_chunks: LegalChunkRepository | None = None,
    contract_chunks: ContractChunkRepository | None = None,
) -> None:
    global _contract_search, _legal_search, _graph, _legal_chunks, _contract_chunks, _graph_rag
    _contract_search = contract_search
    _legal_search = legal_search
    _graph = graph
    _legal_chunks = legal_chunks
    _contract_chunks = contract_chunks
    if legal_search is not None and legal_chunks is not None:
        _graph_rag = LegalGraphRag(legal_search, legal_chunks, graph)
    else:
        _graph_rag = None


def get_contract_search() -> ContractVectorSearch:
    if _contract_search is None:
        raise RuntimeError("ContractVectorSearch not bound — app startup incomplete")
    return _contract_search


def get_legal_search() -> LegalVectorSearch:
    if _legal_search is None:
        raise RuntimeError("LegalVectorSearch not bound — app startup incomplete")
    return _legal_search


def get_graph() -> GraphRepository | None:
    return _graph


def get_graph_rag() -> LegalGraphRag | None:
    return _graph_rag


def get_contract_chunks() -> ContractChunkRepository | None:
    return _contract_chunks
