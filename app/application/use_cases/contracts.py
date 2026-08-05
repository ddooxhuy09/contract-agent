import uuid
from uuid import UUID

from app.core.logging import logger
from app.domain.entities.contract import Contract, ContractChunk
from app.domain.errors import NotFoundError
from app.domain.ports.repositories import ContractChunkRepository, ContractRepository
from app.domain.ports.services import AnalyzePipeline, Embedder, ObjectStorage, QaPipeline
from app.document.chunker import chunk_by_clause
from app.document.parser import parse_document


class UploadContract:
    def __init__(
        self,
        contracts: ContractRepository,
        chunks: ContractChunkRepository,
        storage: ObjectStorage,
        embedder: Embedder,
    ):
        self._contracts = contracts
        self._chunks = chunks
        self._storage = storage
        self._embedder = embedder

    async def execute(self, file_bytes: bytes, filename: str, user_id: UUID) -> dict:
        from pathlib import Path

        ext = Path(filename).suffix.lower()
        allowed = {".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg"}
        if ext not in allowed:
            raise ValueError(f"File type '{ext}' is not supported")

        contract_id = str(uuid.uuid4())
        storage_key = self._storage.save_upload(file_bytes, f"{contract_id}{ext}")
        file_path = self._storage.resolve_path(storage_key)
        status, message, chunk_count = "uploaded", f"File uploaded successfully: {filename}", 0
        full_text: str | None = None
        logger.info("Upload started: contract_id=%s user_id=%s", contract_id, user_id)

        try:
            full_text = parse_document(file_path, ext)
            docs = chunk_by_clause(full_text, contract_id)
            texts = [d.page_content for d in docs]
            vectors = self._embedder.embed_documents(texts) if texts else []
            entities = [
                ContractChunk(
                    contract_id=contract_id,
                    chunk_index=int(d.metadata.get("chunk_index", i + 1)),
                    clause_number=str(d.metadata.get("clause_number", i + 1)),
                    content=d.page_content,
                    embedding=vectors[i] if i < len(vectors) else None,
                )
                for i, d in enumerate(docs)
            ]
            chunk_count = len(entities)
            status, message = "parsed", f"{filename} parsed and indexed with {chunk_count} chunks"
            # FK: upsert the contract row BEFORE inserting chunks so
            # contract_chunks_contract_id_fkey is satisfied.
            self._contracts.upsert(
                Contract(
                    contract_id=contract_id,
                    user_id=user_id,
                    filename=filename or "unknown",
                    file_type=ext,
                    storage_key=storage_key,
                    full_text=full_text,
                    status=status,
                    message=message,
                    chunk_count=chunk_count,
                )
            )
            self._chunks.replace_for_contract(contract_id, entities)
            logger.info("Upload parsed OK: contract_id=%s chunk_count=%s", contract_id, chunk_count)
        except Exception as e:
            logger.error("Upload parse failed: contract_id=%s error=%s", contract_id, e)
            status, message, chunk_count = "uploaded", f"File uploaded but parsing failed: {e}", 0
            self._contracts.upsert(
                Contract(
                    contract_id=contract_id,
                    user_id=user_id,
                    filename=filename or "unknown",
                    file_type=ext,
                    storage_key=storage_key,
                    full_text=None,
                    status=status,
                    message=message,
                    chunk_count=0,
                )
            )

        return {
            "contract_id": contract_id,
            "filename": filename or "unknown",
            "file_type": ext,
            "status": status,
            "message": message,
            "chunk_count": chunk_count,
        }


class AnalyzeContract:
    def __init__(
        self,
        contracts: ContractRepository,
        chunks: ContractChunkRepository,
        pipeline: AnalyzePipeline,
    ):
        self._contracts = contracts
        self._chunks = chunks
        self._pipeline = pipeline

    async def execute(
        self,
        contract_id: str,
        user_id: UUID,
        provider: str = "gemini",
        force: bool = False,
        review_mode: bool = False,
    ) -> dict:
        contract = self._contracts.get_owned(contract_id, user_id)
        if contract is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")

        if not force and contract.analysis is not None and not review_mode:
            return {
                "contract_id": contract_id,
                "analysis": contract.analysis,
                "risks": contract.risks or [],
            }

        full_text = contract.full_text
        if not full_text:
            parts = self._chunks.list_contents(contract_id)
            if not parts:
                raise NotFoundError(f"No documents found for contract: {contract_id}")
            full_text = "\n".join(parts)

        if review_mode:
            # Human-in-the-loop: run analysis but pause before persisting anything.
            draft = await self._pipeline.run_review(full_text, contract_id, provider)
            return {
                "contract_id": contract_id,
                "status": "awaiting_review",
                "review_id": draft["review_id"],
                "draft_analysis": draft["draft_analysis"],
                "draft_risks": draft["draft_risks"],
            }

        analysis, risks = await self._pipeline.run(full_text, contract_id, provider)
        analysis_data = analysis.model_dump() if hasattr(analysis, "model_dump") else analysis
        risk_data = [r.model_dump() if hasattr(r, "model_dump") else r for r in risks]
        self._contracts.save_analysis(contract_id, analysis_data, risk_data)
        return {"contract_id": contract_id, "analysis": analysis_data, "risks": risk_data}


class ResumeAnalysisReview:
    def __init__(
        self,
        contracts: ContractRepository,
        pipeline: AnalyzePipeline,
    ):
        self._contracts = contracts
        self._pipeline = pipeline

    async def execute(
        self,
        contract_id: str,
        review_id: str,
        user_id: UUID,
        approved: bool,
        edits: list | None = None,
    ) -> dict:
        if self._contracts.get_owned(contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        result = await self._pipeline.resume_review(contract_id, review_id, approved, edits)
        if not approved:
            # Rejected: keep the draft available but do not persist as authoritative.
            return {
                "contract_id": contract_id,
                "status": "review_rejected",
                "approved": False,
                "analysis": result["analysis"].model_dump() if hasattr(result["analysis"], "model_dump") else result["analysis"],
                "risks": [r.model_dump() if hasattr(r, "model_dump") else r for r in result["risks"]],
            }
        analysis_data = result["analysis"].model_dump() if hasattr(result["analysis"], "model_dump") else result["analysis"]
        risk_data = [r.model_dump() if hasattr(r, "model_dump") else r for r in result["risks"]]
        self._contracts.save_analysis(contract_id, analysis_data, risk_data)
        return {
            "contract_id": contract_id,
            "status": "approved",
            "approved": True,
            "analysis": analysis_data,
            "risks": risk_data,
        }


class ListContracts:
    def __init__(self, contracts: ContractRepository):
        self._contracts = contracts

    def execute(self, user_id: UUID) -> dict:
        items = self._contracts.list_by_user(user_id)
        return {
            "contracts": [
                {
                    "contract_id": c.contract_id,
                    "filename": c.filename,
                    "status": c.status,
                    "chunk_count": c.chunk_count,
                    "created_at": c.created_at.isoformat() if c.created_at else "",
                }
                for c in items
            ]
        }


class ChatWithContract:
    def __init__(self, contracts: ContractRepository, qa: QaPipeline):
        self._contracts = contracts
        self._qa = qa

    async def execute(
        self,
        contract_id: str,
        question: str,
        user_id: UUID,
        provider: str = "gemini",
        checkpoint_id: str | None = None,
    ) -> dict:
        if self._contracts.get_owned(contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        return await self._qa.answer(contract_id, question, provider, checkpoint_id=checkpoint_id)


class GetChatHistory:
    def __init__(self, contracts: ContractRepository, qa: QaPipeline):
        self._contracts = contracts
        self._qa = qa

    async def execute(self, contract_id: str, user_id: UUID) -> dict:
        if self._contracts.get_owned(contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        messages = await self._qa.history(contract_id)
        return {"contract_id": contract_id, "messages": messages}


class GetChatStates:
    """Time-travel debug: list every persisted checkpoint of the chat thread."""

    def __init__(self, contracts: ContractRepository, qa: QaPipeline):
        self._contracts = contracts
        self._qa = qa

    async def execute(self, contract_id: str, user_id: UUID) -> dict:
        if self._contracts.get_owned(contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        states = await self._qa.state_history(contract_id)
        return {"contract_id": contract_id, "states": states}


class RewindChat:
    """Time-travel: validate a checkpoint of the chat thread and return its snapshot."""

    def __init__(self, contracts: ContractRepository, qa: QaPipeline):
        self._contracts = contracts
        self._qa = qa

    async def execute(self, contract_id: str, checkpoint_id: str, user_id: UUID) -> dict:
        if self._contracts.get_owned(contract_id, user_id) is None:
            raise NotFoundError(f"No documents found for contract: {contract_id}")
        return await self._qa.rewind(contract_id, checkpoint_id)
