import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.checkpointer import close_checkpointer, init_checkpointer
from app.api.routes import router
from app.core.logging import logger
from app.core.settings import get_settings
from app.infrastructure.agents.pipelines import LangGraphAnalyzePipeline, LangGraphQaPipeline
from app.infrastructure.container import build_container
from app.infrastructure.db.schema_loader import apply_postgres_schema
from app.infrastructure.retrieval.context import bind_retrieval

_DEFAULT_JWT_SECRET = "change-me-in-production"


def _validate_security_settings() -> None:
    settings = get_settings()
    if not settings.jwt_secret or settings.jwt_secret == _DEFAULT_JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET must be set to a non-default, non-empty value in the environment / .env. "
            "Refusing to start with a forgeable JWT secret."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ContractLens...")
    _validate_security_settings()
    container = build_container()
    try:
        apply_postgres_schema()
    except Exception as e:
        logger.warning("Postgres schema apply failed (is Docker Postgres up?): %s", e)
    try:
        container.graph.ensure_schema()
    except Exception as e:
        logger.warning("Neo4j unavailable at startup: %s", e)
    container.analyze_pipeline = LangGraphAnalyzePipeline()
    container.qa_pipeline = LangGraphQaPipeline()
    bind_retrieval(
        container.contract_search,
        container.legal_search,
        container.graph,
        legal_chunks=container.legal_chunks,
        contract_chunks=container.contract_chunks,
    )
    app.state.container = container
    try:
        await init_checkpointer()
    except Exception as e:
        logger.warning("Checkpointer init failed: %s", e)
    # Warm embeddings once at startup so upload/analyze don't race HF downloads.
    try:
        await asyncio.to_thread(container.embedder.embed_query, "warmup")
        logger.info("Embeddings model warmed up")
    except Exception as e:
        logger.warning("Embeddings warmup failed (first request will retry): %s", e)
    logger.info("ContractLens ready")
    try:
        yield
    finally:
        try:
            await close_checkpointer()
        except Exception:
            pass
        close = getattr(container.graph, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass



app = FastAPI(
    title="ContractLens",
    description="Hệ thống AI rà soát hợp đồng tiếng Việt",
    version="3.0.0",
    lifespan=lifespan,
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ContractLens", "version": "3.0.0"}


frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    logger.info("Serving frontend from %s", frontend_path)
else:
    logger.warning("Frontend not found at %s", frontend_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
