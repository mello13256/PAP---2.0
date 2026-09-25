# -*- mode: python ; coding: utf-8 -*-
# Especificação do PyInstaller para o MultiMind.exe.
#
# Compilar (a partir de backend/, depois de "npm run build" no frontend):
#     pyinstaller packaging/multimind.spec --noconfirm
#
# Resultado: dist/MultiMind.exe (um único ficheiro, sem precisar de Python/Node).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

BACKEND = Path(SPECPATH).parent
FRONTEND_DIST = BACKEND.parent / "frontend" / "dist"
if not (FRONTEND_DIST / "index.html").exists():
    raise SystemExit("Falta a interface compilada: corre 'npm run build' em frontend/ primeiro.")

datas = [
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(BACKEND / "pricing.json"), "."),
    (str(FRONTEND_DIST), "frontend_dist"),
]

hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + collect_submodules("alembic", filter=lambda name: not name.startswith("alembic.testing"))
    + [
        "aiosqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "email_validator",
        "argon2",
    ]
)

a = Analysis(
    [str(BACKEND / "desktop_main.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["pytest", "ruff", "IPython", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MultiMind",
    icon=str(BACKEND / "packaging" / "multimind.ico"),
    console=False,  # aplicação de janela (sem consola preta)
    upx=False,
    strip=False,
    runtime_tmpdir=None,
)
