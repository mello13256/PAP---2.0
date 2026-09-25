"""Validação de caminhos de ficheiros do workspace.

Os caminhos vêm de modelos de linguagem, por isso são tratados como input não
confiável: nada de caminhos absolutos, ``..``, nomes estranhos ou extensões
executáveis. Isto impede, por exemplo, que um agente escreva fora do projeto.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.core.errors import AppError

MAX_PATH_LENGTH = 200
MAX_DEPTH = 8
MAX_FILE_BYTES = 200_000
MAX_FILES_PER_PROJECT = 200

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sql",
    ".csv",
    ".xml",
    ".svg",
    ".sh",
    ".env.example",
}
ALLOWED_BARE_NAMES = {"Dockerfile", "Makefile", "LICENSE", "README", ".gitignore", ".env.example"}

_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")


class InvalidPathError(AppError):
    status_code = 400
    code = "invalid_path"


def normalize_path(raw: str) -> str:
    """Devolve o caminho normalizado ("src/api.py") ou lança InvalidPathError."""
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidPathError("Caminho vazio")
    path = raw.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise InvalidPathError(f"Caminho absoluto não permitido: {raw}")
    if len(path) > MAX_PATH_LENGTH:
        raise InvalidPathError("Caminho demasiado longo")

    parts = [p for p in path.split("/") if p != ""]
    if not parts:
        raise InvalidPathError("Caminho vazio")
    if len(parts) > MAX_DEPTH:
        raise InvalidPathError("Demasiadas pastas no caminho")
    for part in parts:
        if part in (".", ".."):
            raise InvalidPathError(f"Caminho inválido: {raw}")
        if part != ".gitignore" and part != ".env.example" and not _SEGMENT.match(part):
            raise InvalidPathError(f"Nome inválido no caminho: {part!r}")
        if part.lower() in (".git", ".env"):
            raise InvalidPathError(f"Nome reservado: {part}")

    name = parts[-1]
    suffix = PurePosixPath(name).suffix
    if name not in ALLOWED_BARE_NAMES and suffix.lower() not in ALLOWED_EXTENSIONS:
        raise InvalidPathError(f"Tipo de ficheiro não permitido: {name}")
    return "/".join(parts)
