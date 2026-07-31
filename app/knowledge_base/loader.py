"""Legal KB helpers — dump-based FAISS loader removed. Use IngestLegalDocument."""

from app.core.logging import logger


def load_legal_documents() -> int:
    logger.warning(
        "load_legal_documents() is deprecated. "
        "Ingest via app.application.use_cases.legal_ingest.IngestLegalDocument into Postgres/pgvector."
    )
    return 0
