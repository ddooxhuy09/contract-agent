from typing import Optional, Union
from uuid import UUID

import psycopg
import psycopg2
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

from app.agents.llm_client import DEFAULT_PROVIDER, get_providers, resolve_provider
from app.api.deps import get_container_dep, get_current_user_id
from app.api.login_throttle import LoginThrottle
from app.application.use_cases.auth import MIN_PASSWORD_LENGTH, LoginUser, RegisterUser
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
from app.core.settings import get_settings
from app.domain.errors import AnalysisFailedError, AuthError, ConflictError, NotFoundError
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


def _analysis_failed(e: AnalysisFailedError) -> HTTPException:
    logger.error("Analysis failed: %s", e)
    return HTTPException(
        status_code=502,
        detail="Không trích xuất được điều khoản từ hợp đồng. Vui lòng thử lại hoặc kiểm tra nội dung tệp.",
    )


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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)  # no length floor: accounts made under the old 6-char rule must still log in


class RegisterRequest(LoginRequest):
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)


_login_throttle = LoginThrottle(get_settings().login_max_failures, get_settings().login_window_seconds)


@router.get("/models")
async def list_models():
    """Public list of analysis modes. Aliases only — never leak vendor model names."""
    return [
        {
            "provider": info.get("public_id") or key,
            "label": info.get("alias", "Chuẩn"),
        }
        for key, info in get_providers().items()
    ]


@router.post("/auth/register")
async def register(req: RegisterRequest, container: AppContainer = Depends(get_container_dep)):
    try:
        return RegisterUser(container.users, container.password_hasher, container.tokens).execute(
            req.email, req.password
        )
    except ConflictError as e:
        # Same wording as any other refusal: do not confirm which emails already have an account.
        logger.info("Register refused: %s", e)
        raise HTTPException(
            status_code=400, detail="Không thể đăng ký với thông tin này. Nếu đã có tài khoản, hãy đăng nhập."
        ) from e
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/auth/login")
async def login(req: LoginRequest, request: Request, container: AppContainer = Depends(get_container_dep)):
    key = f"{request.client.host if request.client else '?'}|{req.email.lower()}"
    wait = _login_throttle.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.",
            headers={"Retry-After": str(wait)},
        )
    try:
        result = LoginUser(container.users, container.password_hasher, container.tokens).execute(
            req.email, req.password
        )
    except AuthError as e:
        _login_throttle.record_failure(key)
        raise HTTPException(status_code=401, detail=str(e)) from e
    _login_throttle.reset(key)
    return result


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    max_mb = get_settings().max_upload_mb
    data = await file.read(max_mb * 1024 * 1024 + 1)  # never pull more than the cap into memory
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Tệp quá lớn (tối đa {max_mb} MB).")
    try:
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
        ).execute(req.contract_id, user_id, resolve_provider(req.provider), req.force, req.review_mode)
        if result.get("status") == "awaiting_review":
            return AnalyzeReviewResponse(**result)
        return AnalyzeResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AnalysisFailedError as e:
        raise _analysis_failed(e) from e
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
    except AnalysisFailedError as e:
        raise _analysis_failed(e) from e
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
            req.contract_id, req.question, user_id, resolve_provider(req.provider), req.checkpoint_id
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
                req.contract_id, req.question, resolve_provider(req.provider), req.checkpoint_id
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
