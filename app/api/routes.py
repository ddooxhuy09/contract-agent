from typing import Optional, Union
from uuid import UUID

import psycopg
import psycopg2
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from app.agents.llm_client import DEFAULT_PROVIDER, PROVIDERS
from app.api.deps import get_container_dep, get_current_user_id
from app.application.use_cases.auth import LoginUser, RegisterUser
from app.application.use_cases.contracts import (
    AnalyzeContract,
    ChatWithContract,
    GetChatHistory,
    GetChatStates,
    ListContracts,
    ResumeAnalysisReview,
    RewindChat,
    UploadContract,
)
from app.core.logging import logger
from app.domain.errors import AuthError, ConflictError, NotFoundError
from app.infrastructure.container import AppContainer
from app.schemas.contract import (
    AnalyzeResponse,
    AnalyzeReviewResponse,
    ChatHistoryResponse,
    ChatResponse,
    ChatRewindRequest,
    ChatRewindResponse,
    ChatStatesResponse,
    ContractListResponse,
    ResumeAnalysisRequest,
    ResumeAnalysisResponse,
    UploadResponse,
)

router = APIRouter(prefix="/api/v1")

_DB_UNAVAILABLE_ERRORS = (
    psycopg.OperationalError,
    psycopg.InterfaceError,
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
)


def _http_error(e: Exception) -> HTTPException:
    """Map an unhandled exception to a client-safe HTTPException.

    Never echo ``str(e)`` back: a driver error carries the failing SQL, column
    names and the database host. A dropped/recycled Postgres connection is a
    transient condition, so it maps to 503 (retryable) rather than 500.
    """
    if isinstance(e, _DB_UNAVAILABLE_ERRORS):
        logger.exception("Database unavailable")
        return HTTPException(
            status_code=503,
            detail="Dịch vụ tạm thời không khả dụng, vui lòng thử lại.",
        )
    logger.exception("Unhandled error")
    return HTTPException(status_code=500, detail="Đã xảy ra lỗi nội bộ.")


class AnalyzeRequest(BaseModel):
    contract_id: str
    provider: str = DEFAULT_PROVIDER
    force: bool = False
    review_mode: bool = False


class ChatRequest(BaseModel):
    contract_id: str
    question: str
    provider: str = DEFAULT_PROVIDER
    checkpoint_id: Optional[str] = None


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


@router.get("/models")
async def list_models():
    return [{"provider": key, **info} for key, info in PROVIDERS.items()]


@router.post("/auth/register")
async def register(req: AuthRequest, container: AppContainer = Depends(get_container_dep)):
    try:
        return RegisterUser(container.users, container.password_hasher, container.tokens).execute(
            req.email, req.password
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/auth/login")
async def login(req: AuthRequest, container: AppContainer = Depends(get_container_dep)):
    try:
        return LoginUser(container.users, container.password_hasher, container.tokens).execute(
            req.email, req.password
        )
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        data = await file.read()
        result = await UploadContract(
            container.contracts,
            container.contract_chunks,
            container.storage,
            container.embedder,
        ).execute(data, file.filename or "unknown", user_id)
        return UploadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.post("/analyze", response_model=Union[AnalyzeResponse, AnalyzeReviewResponse])
async def analyze(
    req: AnalyzeRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.analyze_pipeline is not None
        result = await AnalyzeContract(
            container.contracts,
            container.contract_chunks,
            container.analyze_pipeline,
        ).execute(req.contract_id, user_id, req.provider, req.force, req.review_mode)
        if result.get("status") == "awaiting_review":
            return AnalyzeReviewResponse(**result)
        return AnalyzeResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.post("/analyze/resume", response_model=ResumeAnalysisResponse)
async def resume_analysis(
    req: ResumeAnalysisRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.analyze_pipeline is not None
        result = await ResumeAnalysisReview(
            container.contracts,
            container.analyze_pipeline,
        ).execute(req.contract_id, req.review_id, user_id, req.approved, req.edits)
        return ResumeAnalysisResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.get("/contracts", response_model=ContractListResponse)
async def contracts(
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        return ContractListResponse(**ListContracts(container.contracts).execute(user_id))
    except Exception as e:
        raise _http_error(e) from e


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        result = await ChatWithContract(container.contracts, container.qa_pipeline).execute(
            req.contract_id, req.question, user_id, req.provider, req.checkpoint_id
        )
        return ChatResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        # Ownership check must happen before streaming starts so a 404 is a real
        # HTTP error, not a broken SSE stream.
        if container.contracts.get_owned(req.contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {req.contract_id}")

        async def event_gen():
            async for frame in container.qa_pipeline.stream(
                req.contract_id, req.question, req.provider, req.checkpoint_id
            ):
                yield frame

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.get("/chat/{contract_id}/history", response_model=ChatHistoryResponse)
async def chat_history(
    contract_id: str,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        result = await GetChatHistory(container.contracts, container.qa_pipeline).execute(
            contract_id, user_id
        )
        return ChatHistoryResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.get("/chat/{contract_id}/states", response_model=ChatStatesResponse)
async def chat_states(
    contract_id: str,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        result = await GetChatStates(container.contracts, container.qa_pipeline).execute(
            contract_id, user_id
        )
        return ChatStatesResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e


@router.post("/chat/{contract_id}/rewind", response_model=ChatRewindResponse)
async def chat_rewind(
    contract_id: str,
    req: ChatRewindRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        result = await RewindChat(container.contracts, container.qa_pipeline).execute(
            contract_id, req.checkpoint_id, user_id
        )
        return ChatRewindResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise _http_error(e) from e
