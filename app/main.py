import asyncio
import sys
from pathlib import Path

# psycopg (async) requires a selector-based event loop; Windows defaults to
# ProactorEventLoop, which makes AsyncConnectionPool hang/timeout. Must be set before
# any event loop is created, so this runs at module import time, ahead of uvicorn's own
# loop setup and any DB/checkpointer connections.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.checkpointer import close_checkpointer, init_checkpointer
from app.api.routes import router
from app.core.config import logger
from app.core.database import init_db

app = FastAPI(title="ContractLens", description="Hệ thống AI rà soát hợp đồng tiếng Việt", version="2.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.on_event("startup")
async def startup():
    logger.info("Initializing ContractLens...")
    init_db()
    await init_checkpointer()
    logger.info("ContractLens ready")


@app.on_event("shutdown")
async def shutdown():
    await close_checkpointer()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ContractLens", "version": "2.0.0"}


frontend_path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    logger.info(f"Serving frontend from {frontend_path}")
else:
    logger.warning(f"Frontend not found at {frontend_path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
