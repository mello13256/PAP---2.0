from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.service import create_default_agents
from app.auth.models import User
from app.auth.schemas import RegisterRequest
from app.auth.security import hash_password, verify_password
from app.core.errors import AuthenticationError, ConflictError


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(session: AsyncSession, data: RegisterRequest) -> User:
    email = _normalize_email(data.email)
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("Já existe uma conta com este email")

    user = User(
        email=email,
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
    )
    session.add(user)
    await session.commit()
    # Cada utilizador novo começa com os agentes pré-definidos (Granite, Qwen, Simulado).
    await create_default_agents(session, user)
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == _normalize_email(email)))
    # verify_password corre sempre (mesmo sem utilizador) para não revelar se o email existe.
    if not verify_password(user.password_hash if user else None, password) or user is None:
        raise AuthenticationError("Email ou password incorretos")
    return user
