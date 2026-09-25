"""Aplicação das migrações Alembic a partir do código (usado no arranque da app)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.core.paths import ALEMBIC_DIR, ALEMBIC_INI


def upgrade_to_head(database_url: str) -> None:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
