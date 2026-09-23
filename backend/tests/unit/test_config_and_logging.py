import logging

import pytest

from app.core.config import Settings
from app.core.logging import SecretRedactingFilter


def test_empty_api_key_is_treated_as_not_configured() -> None:
    settings = Settings(_env_file=None, openai_api_key="", secret_key="x" * 20)
    assert settings.openai_api_key is None


def test_secret_key_is_generated_in_development() -> None:
    settings = Settings(_env_file=None, environment="development")
    assert settings.secret_key is not None
    assert len(settings.secret_key.get_secret_value()) > 30


def test_secret_key_is_required_in_production() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, environment="production")


def test_secrets_are_not_shown_in_repr() -> None:
    settings = Settings(_env_file=None, openai_api_key="sk-very-secret-value", secret_key="k" * 20)
    assert "sk-very-secret-value" not in repr(settings)


def test_logging_filter_redacts_secrets() -> None:
    record = logging.LogRecord(
        "t", logging.ERROR, __file__, 1, "falhou com a chave %s", ("sk-very-secret-value",), None
    )
    SecretRedactingFilter(["sk-very-secret-value"]).filter(record)
    assert record.getMessage() == "falhou com a chave ***"
