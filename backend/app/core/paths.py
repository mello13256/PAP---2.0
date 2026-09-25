"""Onde ficam os ficheiros, em desenvolvimento e na versão .exe.

Há dois tipos de ficheiros:

- **Recursos** (só leitura, vêm com a aplicação): migrações, preços, interface
  compilada. Em desenvolvimento estão no repositório; no .exe estão dentro do
  próprio executável (o PyInstaller extrai-os para uma pasta temporária,
  ``sys._MEIPASS``).
- **Dados** (escrita): base de dados, workspaces, chave de sessão, logs, .env.
  Em desenvolvimento ficam em ``backend/data``; no .exe ficam em
  ``%LOCALAPPDATA%\\MultiMind`` (sobrevivem a atualizações do .exe).
  Pode ser forçado com a variável ``MULTIMIND_DATA_DIR``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BACKEND_DIR))


def _data_dir() -> Path:
    override = os.environ.get("MULTIMIND_DATA_DIR")
    if override:
        return Path(override)
    if FROZEN:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        return Path(base) / "MultiMind"
    return BACKEND_DIR / "data"


DATA_DIR = _data_dir()

FRONTEND_DIST = RESOURCE_DIR / "frontend_dist" if FROZEN else REPO_ROOT / "frontend" / "dist"
ENV_FILE = DATA_DIR / ".env" if FROZEN else REPO_ROOT / ".env"
DEFAULT_WORKSPACES = DATA_DIR / "workspaces" if FROZEN else REPO_ROOT / "workspaces"
PRICING_FILE = RESOURCE_DIR / "pricing.json"
ALEMBIC_INI = RESOURCE_DIR / "alembic.ini"
ALEMBIC_DIR = RESOURCE_DIR / "alembic"
