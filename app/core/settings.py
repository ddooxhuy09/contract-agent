from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # BAAI/bge-m3 via LangChain HuggingFaceEmbeddings
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_device: str = "auto"  # CUDA if available, else CPU
    embedding_trust_remote_code: bool = True
    embedding_normalize: bool = True
    embedding_max_seq_length: int = 512

    database_url: str = "postgresql://contractlens:contractlens@localhost:5432/contractlens"
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    db_pool_timeout: float = 10.0
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "contractlens"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    upload_dir: str = "data/uploads"
    # Comma-separated allowlist of frontend origins (no trailing slash). Local
    # Vite dev server by default; extend for deployed frontend domains.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # ~300–400 Vietnamese words ≈ 1600–2200 chars; used for contract Điều splits
    max_chunk_size: int = 1800
    chunk_overlap: int = 120
    top_k_retrieval: int = 5
    similarity_threshold: float = 0.6

    schema_sql_path: str = "schema.sql"
    schema_cypher_path: str = "schema.cypher"

    # GraphRAG hierarchy expand: neo4j | postgres | both (merge, prefer neo4j then fill gaps)
    legal_expand_backend: str = "neo4j"

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
