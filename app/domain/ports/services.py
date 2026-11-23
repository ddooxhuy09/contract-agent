from typing import Any, Protocol
from uuid import UUID

from app.domain.entities.search import RetrievedChunk


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    def complete(self, prompt: str) -> str: ...
    async def acomplete(self, prompt: str) -> str: ...


class ObjectStorage(Protocol):
    def save_upload(self, data: bytes, filename: str, content_type: str | None = None) -> str: ...
    def resolve_path(self, storage_key: str) -> str: ...
    def delete(self, storage_key: str) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


class TokenService(Protocol):
    def create_access_token(self, user_id: UUID, email: str) -> str: ...
    def parse_access_token(self, token: str) -> dict[str, Any]: ...


class ContractVectorSearch(Protocol):
    def search(self, query: str, contract_id: str, k: int) -> list[RetrievedChunk]: ...


class LegalVectorSearch(Protocol):
    def search(
        self,
        query: str,
        k: int,
        min_score: float | None = None,
        doc_type_hint: str | None = None,
        doc_ids: list[str] | None = None,
        doc_nums: list[str] | None = None,
    ) -> list[RetrievedChunk]: ...

    def search_in_docs(self, query: str, doc_ids: list[str], k: int = 2) -> list[RetrievedChunk]: ...

    def search_in_doc_nums(self, query: str, doc_nums: list[str], k: int = 3) -> list[RetrievedChunk]: ...


class AnalyzePipeline(Protocol):
    async def run(
        self, full_text: str, contract_id: str, provider: str = "gemini"
    ) -> tuple[Any, list[Any]]: ...

    async def run_review(
        self, full_text: str, contract_id: str, provider: str = "gemini"
    ) -> dict[str, Any]: ...

    async def resume_review(
        self,
        contract_id: str,
        review_id: str,
        approved: bool,
        edits: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


class QaPipeline(Protocol):
    async def answer(
        self, contract_id: str, question: str, provider: str = "gemini", checkpoint_id: str | None = None
    ) -> dict[str, Any]: ...
    async def history(self, contract_id: str) -> list[dict[str, Any]]: ...
    async def state_history(self, contract_id: str) -> list[dict[str, Any]]: ...
    async def rewind(self, contract_id: str, checkpoint_id: str) -> dict[str, Any]: ...
    def stream(
        self, contract_id: str, question: str, provider: str = "gemini", checkpoint_id: str | None = None
    ) -> Any: ...
