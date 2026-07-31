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
    ) -> list[RetrievedChunk]: ...

    def search_in_docs(self, query: str, doc_ids: list[str], k: int = 2) -> list[RetrievedChunk]: ...


class GraphRepository(Protocol):
    def ensure_schema(self) -> None: ...
    def upsert_document_tree(
        self,
        doc_id: str,
        doc_num: str,
        doc_type: str,
        nodes: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> None: ...
    def upsert_doc_relations(self, relations: list[dict[str, str]]) -> None: ...
    def upsert_chunk_relations(self, relations: list[dict[str, str]]) -> None: ...
    def expand(self, chunk_refs: list[str], limit: int = 80) -> dict[str, Any]: ...


class AnalyzePipeline(Protocol):
    async def run(
        self, full_text: str, contract_id: str, provider: str = "gemini"
    ) -> tuple[Any, list[Any]]: ...


class QaPipeline(Protocol):
    async def answer(self, contract_id: str, question: str, provider: str = "gemini") -> dict[str, Any]: ...
    async def history(self, contract_id: str) -> list[dict[str, Any]]: ...
