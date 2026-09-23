from app.core.config import Settings
from app.providers.setup import build_registry


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, secret_key="k" * 20, **kwargs)


def test_only_configured_providers_are_registered() -> None:
    registry = build_registry(_settings(ollama_enabled=False))
    assert registry.available() == ["fake"]


def test_providers_with_keys_are_registered() -> None:
    registry = build_registry(
        _settings(openai_api_key="sk-test", gemini_api_key="g-test", github_models_token="gh")
    )
    assert registry.available() == ["fake", "gemini", "github_models", "ollama", "openai"]
    assert registry.get("gemini").name == "gemini"
