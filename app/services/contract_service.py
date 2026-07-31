"""Legacy facade — prefer application use cases via routes."""

from uuid import UUID

from fastapi import UploadFile

from app.application.use_cases.contracts import (
    AnalyzeContract,
    ChatWithContract,
    GetChatHistory,
    ListContracts,
    UploadContract,
)
from app.infrastructure.agents.pipelines import LangGraphAnalyzePipeline, LangGraphQaPipeline
from app.infrastructure.container import build_container
from app.infrastructure.retrieval.context import bind_retrieval
from app.schemas.contract import (
    AnalyzeResponse,
    ChatHistoryResponse,
    ChatResponse,
    ContractListResponse,
    UploadResponse,
)

_container = None


def _get_container():
    global _container
    if _container is None:
        _container = build_container()
        _container.analyze_pipeline = LangGraphAnalyzePipeline()
        _container.qa_pipeline = LangGraphQaPipeline()
        bind_retrieval(
            _container.contract_search,
            _container.legal_search,
            _container.graph,
            legal_chunks=_container.legal_chunks,
            contract_chunks=_container.contract_chunks,
        )
    return _container


async def upload_contract(file: UploadFile, user_id: str) -> UploadResponse:
    c = _get_container()
    data = await file.read()
    result = await UploadContract(c.contracts, c.contract_chunks, c.storage, c.embedder).execute(
        data, file.filename or "unknown", UUID(user_id)
    )
    return UploadResponse(**result)


async def analyze_contract(contract_id: str, user_id: str, provider: str = "gemini", force: bool = False) -> AnalyzeResponse:
    c = _get_container()
    assert c.analyze_pipeline is not None
    result = await AnalyzeContract(c.contracts, c.contract_chunks, c.analyze_pipeline).execute(
        contract_id, UUID(user_id), provider, force
    )
    return AnalyzeResponse(**result)


async def list_contracts(user_id: str) -> ContractListResponse:
    c = _get_container()
    return ContractListResponse(**ListContracts(c.contracts).execute(UUID(user_id)))


async def chat_with_contract(contract_id: str, question: str, user_id: str, provider: str = "gemini") -> ChatResponse:
    c = _get_container()
    assert c.qa_pipeline is not None
    result = await ChatWithContract(c.contracts, c.qa_pipeline).execute(
        contract_id, question, UUID(user_id), provider
    )
    return ChatResponse(**result)


async def get_chat_history(contract_id: str, user_id: str) -> ChatHistoryResponse:
    c = _get_container()
    assert c.qa_pipeline is not None
    result = await GetChatHistory(c.contracts, c.qa_pipeline).execute(contract_id, UUID(user_id))
    return ChatHistoryResponse(**result)
