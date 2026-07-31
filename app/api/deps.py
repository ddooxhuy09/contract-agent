from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from app.application.use_cases.auth import ResolveUserId
from app.domain.errors import AuthError
from app.infrastructure.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


async def get_current_user_id(
    request: Request,
    authorization: str | None = Header(default=None),
) -> UUID:
    container: AppContainer = request.app.state.container
    try:
        return ResolveUserId(container.tokens).execute(authorization)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


def get_container_dep(request: Request) -> AppContainer:
    return get_container(request)
