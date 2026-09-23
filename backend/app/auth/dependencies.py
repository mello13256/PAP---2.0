from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.security import decode_session_token
from app.core.errors import AuthenticationError
from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    settings = request.app.state.settings
    token = request.cookies.get(settings.session_cookie_name)
    user_id = decode_session_token(token, settings) if token else None
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise AuthenticationError("Sessão inválida ou expirada")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
