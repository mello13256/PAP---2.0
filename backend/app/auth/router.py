from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response, status

from app.auth import service
from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.schemas import LoginRequest, RegisterRequest, UserOut
from app.auth.security import create_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(request: Request, response: Response, user_id: uuid.UUID) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.session_cookie_name,
        create_session_token(user_id, settings),
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,  # inacessível a JavaScript (protege contra XSS)
        samesite="lax",  # não é enviado em pedidos POST de outros sites (CSRF)
        secure=settings.is_production,  # só HTTPS em produção
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, request: Request, response: Response, session: SessionDep
) -> UserOut:
    user = await service.register_user(session, data)
    _start_session(request, response, user.id)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login(
    data: LoginRequest, request: Request, response: Response, session: SessionDep
) -> UserOut:
    user = await service.authenticate(session, data.email, data.password)
    _start_session(request, response, user.id)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    response.delete_cookie(request.app.state.settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
