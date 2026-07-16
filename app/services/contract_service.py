import psycopg2
from fastapi import UploadFile
from psycopg2.extras import Json
from app.core.config import logger
from app.core.database import get_db
from app.schemas.contract import (
    UploadResponse,
    AnalyzeResponse,
    ChatResponse,
    ChatHistoryResponse,
    ContractSummary,
    ContractListResponse,
)
from app.document.file_handler import save_upload
from app.document.parser import parse_document
from app.document.chunker import chunk_by_clause
from app.vectorstore.faiss_store import get_contract_collection
from app.agents.workflow import run_analysis_workflow
from app.agents.qa_agent import answer_question, get_conversation_history
from app.agents.llm_client import DEFAULT_PROVIDER


def _assert_owns_contract(contract_id: str, user_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT 1 FROM uploaded_contracts WHERE contract_id = %s AND user_id = %s", (contract_id, user_id))
            except psycopg2.DataError:
                # contract_id isn't even a valid UUID (e.g. malformed/typo'd input) — treat
                # it the same as "not found" instead of leaking a raw SQL error as a 500.
                raise ValueError(f"No documents found for contract: {contract_id}")
            if cur.fetchone() is None:
                raise ValueError(f"No documents found for contract: {contract_id}")


async def upload_contract(file: UploadFile, user_id: str) -> UploadResponse:
    contract_id, file_path, file_ext = await save_upload(file)
    filename = file.filename or "unknown"
    status, message, chunk_count = "uploaded", f"File uploaded successfully: {filename}", 0
    logger.info(f"Upload started: contract_id={contract_id} user_id={user_id} filename={filename!r} ext={file_ext}")

    try:
        text = parse_document(file_path, file_ext)
        docs = chunk_by_clause(text, contract_id)
        get_contract_collection().add_documents(docs)
        chunk_count = len(docs)
        status, message = "parsed", f"{filename} parsed and indexed with {chunk_count} chunks"
        logger.info(f"Upload parsed OK: contract_id={contract_id} chunk_count={chunk_count}")
    except Exception as e:
        logger.error(f"Upload parse failed: contract_id={contract_id} error={e}")
        message = f"File uploaded but parsing failed: {str(e)}"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO uploaded_contracts (contract_id, user_id, filename, file_type, file_path, status, message, chunk_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (contract_id) DO UPDATE SET status = EXCLUDED.status, message = EXCLUDED.message, chunk_count = EXCLUDED.chunk_count",
                (contract_id, user_id, filename, file_ext, file_path, status, message, chunk_count),
            )

    return UploadResponse(contract_id=contract_id, filename=filename, file_type=file_ext, status=status, message=message, chunk_count=chunk_count)


def _load_cached_analysis(contract_id: str) -> AnalyzeResponse | None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis, risks FROM uploaded_contracts WHERE contract_id = %s AND analysis IS NOT NULL",
                (contract_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    analysis, risks = row
    return AnalyzeResponse(contract_id=contract_id, analysis=analysis, risks=risks or [])


def _save_analysis_result(contract_id: str, analysis, risks: list):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE uploaded_contracts SET status = %s, analysis = %s, risks = %s WHERE contract_id = %s",
                ("analyzed", Json(analysis.model_dump()), Json([r.model_dump() for r in risks]), contract_id),
            )


async def analyze_contract(contract_id: str, user_id: str, provider: str = DEFAULT_PROVIDER, force: bool = False) -> AnalyzeResponse:
    logger.info(f"Analyze requested: contract_id={contract_id} user_id={user_id} provider={provider} force={force}")
    _assert_owns_contract(contract_id, user_id)

    if not force:
        cached = _load_cached_analysis(contract_id)
        if cached is not None:
            logger.info(f"Analyze cache hit: contract_id={contract_id} risk_count={len(cached.risks)}")
            return cached

    all_docs = get_contract_collection().get(where={"contract_id": contract_id})
    if not all_docs or not all_docs.get("documents"):
        logger.error(f"Analyze failed: contract_id={contract_id} has no indexed chunks")
        raise ValueError(f"No documents found for contract: {contract_id}")
    full_text = "\n".join(all_docs["documents"])
    logger.info(f"Analyze cache miss, running pipeline: contract_id={contract_id} chunk_count={len(all_docs['documents'])}")
    analysis, risks = await run_analysis_workflow(full_text, contract_id, provider)

    _save_analysis_result(contract_id, analysis, risks)
    logger.info(f"Analyze saved: contract_id={contract_id} risk_count={len(risks)}")

    return AnalyzeResponse(contract_id=contract_id, analysis=analysis.model_dump(), risks=[r.model_dump() for r in risks])


async def list_contracts(user_id: str) -> ContractListResponse:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT contract_id, filename, status, chunk_count, created_at "
                "FROM uploaded_contracts WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()

    contracts = [
        ContractSummary(
            contract_id=str(contract_id),
            filename=filename,
            status=status,
            chunk_count=chunk_count or 0,
            created_at=created_at.isoformat(),
        )
        for contract_id, filename, status, chunk_count, created_at in rows
    ]
    return ContractListResponse(contracts=contracts)


async def chat_with_contract(contract_id: str, question: str, user_id: str, provider: str = DEFAULT_PROVIDER) -> ChatResponse:
    _assert_owns_contract(contract_id, user_id)
    return await answer_question(question, contract_id, provider)


async def get_chat_history(contract_id: str, user_id: str) -> ChatHistoryResponse:
    _assert_owns_contract(contract_id, user_id)
    messages = await get_conversation_history(contract_id)
    return ChatHistoryResponse(contract_id=contract_id, messages=messages)
