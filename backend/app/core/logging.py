"""Configuração de logging com ocultação de segredos.

Mesmo que uma API key acabe por ir parar a uma mensagem de log (por exemplo,
dentro de uma exceção de um SDK), o filtro substitui-a por ``***``.
"""

from __future__ import annotations

import logging

from app.core.config import Settings


class SecretRedactingFilter(logging.Filter):
    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        # Ignora valores muito curtos para não ocultar palavras normais por engano.
        self._secrets = [s for s in secrets if len(s) >= 8]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        message = record.getMessage()
        redacted = message
        for secret in self._secrets:
            redacted = redacted.replace(secret, "***")
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S")
    )
    handler.addFilter(SecretRedactingFilter(settings.secret_values()))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
