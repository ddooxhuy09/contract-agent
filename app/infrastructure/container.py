from dataclasses import dataclass

from app.domain.ports.repositories import (
    ContractChunkRepository,
    ContractRepository,
    LegalChunkRepository,
    LegalDocumentRepository,
    UserRepository,
)
from app.domain.ports.services import (
    AnalyzePipeline,
    ChatModel,
    ContractVectorSearch,
    Embedder,
    GraphRepository,
    LegalVectorSearch,
    ObjectStorage,
    PasswordHasher,
    QaPipeline,
    TokenService,
)
from app.infrastructure.auth.jwt_tokens import JwtTokenService
from app.infrastructure.auth.password import BcryptPasswordHasher
from app.infrastructure.db.contract_chunk_repository import PgContractChunkRepository
from app.infrastructure.db.contract_repository import PgContractRepository
from app.infrastructure.db.legal_repository import PgLegalChunkRepository, PgLegalDocumentRepository
from app.infrastructure.db.user_repository import PgUserRepository
from app.infrastructure.storage.local_storage import LocalObjectStorage
from app.infrastructure.vector.pg_search import PgContractVectorSearch, PgLegalVectorSearch


@dataclass
class AppContainer:
    users: UserRepository
    contracts: ContractRepository
    contract_chunks: ContractChunkRepository
    legal_docs: LegalDocumentRepository
    legal_chunks: LegalChunkRepository
    embedder: Embedder
    chat_model: ChatModel
    storage: ObjectStorage
    password_hasher: PasswordHasher
    tokens: TokenService
    contract_search: ContractVectorSearch
    legal_search: LegalVectorSearch
    graph: GraphRepository
    analyze_pipeline: AnalyzePipeline | None = None
    qa_pipeline: QaPipeline | None = None


def build_container() -> AppContainer:
    # Lazy imports keep test collection light when torch/HF not needed
    from app.infrastructure.embeddings.hf_embedder import HuggingFaceEmbedder
    from app.infrastructure.llm.gemini_chat import GeminiChatModel
    from app.infrastructure.neo4j.graph_repository import Neo4jGraphRepository

    embedder = HuggingFaceEmbedder()
    graph = Neo4jGraphRepository()
    return AppContainer(
        users=PgUserRepository(),
        contracts=PgContractRepository(),
        contract_chunks=PgContractChunkRepository(),
        legal_docs=PgLegalDocumentRepository(),
        legal_chunks=PgLegalChunkRepository(),
        embedder=embedder,
        chat_model=GeminiChatModel(),
        storage=LocalObjectStorage(),
        password_hasher=BcryptPasswordHasher(),
        tokens=JwtTokenService(),
        contract_search=PgContractVectorSearch(embedder),
        legal_search=PgLegalVectorSearch(embedder),
        graph=graph,
    )
