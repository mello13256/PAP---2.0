"""Configuração da aplicação, lida de variáveis de ambiente e do ficheiro .env.

Os segredos (API keys, SECRET_KEY) são guardados como ``SecretStr``: não aparecem
em ``repr()``, em logs, nem em mensagens de erro por acidente.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MultiMind"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    secret_key: SecretStr | None = None
    session_cookie_name: str = "mm_session"
    session_ttl_minutes: int = 60 * 12

    database_url: str = ""
    # Aplica as migrações pendentes no arranque (útil em desenvolvimento e na demo).
    auto_migrate: bool = True

    workspaces_dir: Path = REPO_ROOT / "workspaces"

    # Fornecedores de LLM (todos opcionais). Os URLs são os endpoints compatíveis
    # com a API da OpenAI de cada fornecedor; confirmar na documentação de cada um.
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434/v1"
    github_models_token: SecretStr | None = None
    github_models_base_url: str = "https://models.github.ai/inference"
    gemini_api_key: SecretStr | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    _generated_secret: bool = PrivateAttr(default=False)

    @field_validator(
        "secret_key",
        "openai_api_key",
        "anthropic_api_key",
        "github_models_token",
        "gemini_api_key",
        "groq_api_key",
        mode="before",
    )
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        # No .env, "OPENAI_API_KEY=" significa "não configurado".
        return None if value == "" else value

    @model_validator(mode="after")
    def _apply_defaults(self) -> Settings:
        if not self.database_url:
            data_dir = BACKEND_DIR / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite+aiosqlite:///{(data_dir / 'multimind.db').as_posix()}"

        if self.secret_key is None:
            if self.environment == "production":
                raise ValueError("SECRET_KEY é obrigatória em produção")
            # Chave temporária: as sessões deixam de ser válidas quando o servidor reinicia.
            self.secret_key = SecretStr(secrets.token_urlsafe(48))
            self._generated_secret = True
        return self

    @property
    def secret_key_was_generated(self) -> bool:
        return self._generated_secret

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def secret_values(self) -> list[str]:
        """Todos os valores secretos configurados (usado para os ocultar nos logs)."""
        values = []
        for name, field_value in self:
            if isinstance(field_value, SecretStr) and name != "secret_key":
                values.append(field_value.get_secret_value())
        if self.secret_key is not None:
            values.append(self.secret_key.get_secret_value())
        return [v for v in values if v]


@lru_cache
def get_settings() -> Settings:
    return Settings()
