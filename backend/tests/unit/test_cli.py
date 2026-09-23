from app.cli import main


def test_ping_with_fake_provider(capsys) -> None:
    assert main(["ping", "--provider", "fake", "--model", "fake-model"]) == 0
    out = capsys.readouterr().out
    assert "OK" in out
    assert "sucesso=True" in out


def test_unreachable_provider_reports_a_clean_error(capsys, monkeypatch) -> None:
    # Porta onde não há nada a correr: simula o Ollama desligado.
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9/v1")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        code = main(["models", "--provider", "ollama"])
    finally:
        get_settings.cache_clear()
    assert code == 1
    assert "unavailable" in capsys.readouterr().err
