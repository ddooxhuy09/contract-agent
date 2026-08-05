from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agents.memory import close_memory_store, init_memory_store
from app.core.logging import logger
from app.core.settings import get_settings

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def init_checkpointer() -> None:
    """Open the connection pool and provision the checkpoint tables (idempotent).

    Must be called once during app startup, after the event loop is running —
    psycopg_pool.AsyncConnectionPool cannot be opened at plain import time.
    Also initializes the cross-thread memory store on the same pool.
    """
    global _pool, _checkpointer
    if _checkpointer is not None:
        return
    _pool = AsyncConnectionPool(
        conninfo=get_settings().database_url,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(conn=_pool)
    await _checkpointer.setup()
    await init_memory_store(_pool)
    logger.info("LangGraph Postgres checkpointer initialized")


async def close_checkpointer() -> None:
    global _pool, _checkpointer
    await close_memory_store()
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized; call init_checkpointer() during app startup")
    return _checkpointer
