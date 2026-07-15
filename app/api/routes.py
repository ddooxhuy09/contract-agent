from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.agents.llm_client import DEFAULT_PROVIDER, PROVIDERS
from app.core.auth import get_current_user_id
from app.schemas.contract import AnalyzeResponse, ChatHistoryResponse, ChatResponse, ContractListResponse, UploadResponse
from app.services import analyze_contract, chat_with_contract, get_chat_history, list_contracts, upload_contract

router = APIRouter(prefix="/api/v1")


class AnalyzeRequest(BaseModel):
    contract_id: str
    provider: str = DEFAULT_PROVIDER
    force: bool = False


class ChatRequest(BaseModel):
    contract_id: str
    question: str
    provider: str = DEFAULT_PROVIDER


@router.get("/models")
async def list_models():
    return [{"provider": key, **info} for key, info in PROVIDERS.items()]


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    try:
        return await upload_contract(file, user_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest, user_id: str = Depends(get_current_user_id)):
    try:
        return await analyze_contract(req.contract_id, user_id, req.provider, req.force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts", response_model=ContractListResponse)
async def contracts(user_id: str = Depends(get_current_user_id)):
    try:
        return await list_contracts(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_id: str = Depends(get_current_user_id)):
    try:
        return await chat_with_contract(req.contract_id, req.question, user_id, req.provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/{contract_id}/history", response_model=ChatHistoryResponse)
async def chat_history(contract_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        return await get_chat_history(contract_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
