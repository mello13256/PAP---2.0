"""Aplicação das migrações Alembic a partir do código (usado no arranque da app)."""

from __future__ import annotations

from alembic import command
from alembic.config import Config

from app.core.config import BACKEND_DIR


def upgrade_to_head(database_url: str) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
