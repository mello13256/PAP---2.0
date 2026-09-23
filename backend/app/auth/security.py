"""Hash de passwords (argon2) e tokens de sessão (JWT assinado com SECRET_KEY)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings
from app.db.types import utcnow

_hasher = PasswordHasher()

# Usado quando o email não existe, para que o login demore o mesmo tempo
# nos dois casos (não revela que emails estão registados).
_DUMMY_HASH = _hasher.hash("multimind-dummy-password")

_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_session_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=_ALGORITHM)


def decode_session_token(token: str, settings: Settings) -> uuid.UUID | None:
    """Devolve o id do utilizador, ou None se o token for inválido/expirado."""
    try:
        payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
