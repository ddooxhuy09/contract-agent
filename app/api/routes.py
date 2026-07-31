from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field

from app.agents.llm_client import DEFAULT_PROVIDER, PROVIDERS
from app.api.deps import get_container_dep, get_current_user_id
from app.application.use_cases.auth import LoginUser, RegisterUser
from app.application.use_cases.contracts import (
    AnalyzeContract,
    ChatWithContract,
    GetChatHistory,
    ListContracts,
    UploadContract,
)
from app.domain.errors import AuthError, ConflictError, NotFoundError
from app.infrastructure.container import AppContainer
from app.schemas.contract import (
    AnalyzeResponse,
    ChatHistoryResponse,
    ChatResponse,
    ContractListResponse,
    UploadResponse,
)

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    contract_id: str
    provider: str = DEFAULT_PROVIDER
    force: bool = False


class ChatRequest(BaseModel):
    contract_id: str
    question: str
    provider: str = DEFAULT_PROVIDER


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/analyze", response_model=AnalyzeResponse)
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
        ).execute(req.contract_id, user_id, req.provider, req.force)
        return AnalyzeResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/contracts", response_model=ContractListResponse)
async def contracts(
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        return ContractListResponse(**ListContracts(container.contracts).execute(user_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_id: UUID = Depends(get_current_user_id),
    container: AppContainer = Depends(get_container_dep),
):
    try:
        assert container.qa_pipeline is not None
        result = await ChatWithContract(container.contracts, container.qa_pipeline).execute(
            req.contract_id, req.question, user_id, req.provider
        )
        return ChatResponse(**result)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e
