"""Lançador de ambiente de trabalho (é isto que o MultiMind.exe executa).

1. Prepara a pasta de dados (%LOCALAPPDATA%\\MultiMind) e aplica as migrações.
2. Liga o servidor (API + interface) em http://127.0.0.1:<porta>, só no próprio PC.
3. Abre o browser e mostra uma pequena janela de controlo (Abrir / Pasta de dados / Sair).

Funciona sem internet: tudo corre localmente; os modelos vêm do Ollama local.
Se o MultiMind já estiver aberto, apenas abre o browser (uma só instância).

Opções:
    --no-browser     não abre o browser
    --no-window      sem janela de controlo (fica na consola; Ctrl+C para sair)
    --port N         porta preferida (por defeito 8000)
    --smoke-test     arranca, verifica que responde e termina (usado na compilação)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from app.core.paths import DATA_DIR, FROZEN

APP_NAME = "MultiMind"
DEFAULT_PORT = 8000


def _prepare_io() -> Path:
    """Num .exe sem consola, stdout/stderr não existem: redireciona para um ficheiro."""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "multimind.log"
    if sys.stdout is None or sys.stderr is None:
        stream = open(log_file, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    return log_file


def _health(port: int, timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except (OSError, ValueError):
        return None


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _choose_port(preferred: int) -> int:
    if _port_free(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerThread(threading.Thread):
    def __init__(self, port: int) -> None:
        super().__init__(name="multimind-server", daemon=True)
        import uvicorn

        from app.main import create_app

        self.port = port
        config = uvicorn.Config(
            create_app(),
            host="127.0.0.1",
            port=port,
            log_config=None,  # usamos o nosso logging (e não há consola no .exe)
            lifespan="on",
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True

    def wait_ready(self, timeout: float = 60.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_alive():
                return False
            if _health(self.port):
                return True
            time.sleep(0.25)
        return False


def _open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])  # noqa: S603, S607
    else:
        subprocess.Popen(["xdg-open", str(path)])  # noqa: S603, S607


def _ollama_running() -> bool:
    from app.core.config import get_settings
    from app.models_manager.service import native_base_url

    url = native_base_url(get_settings().ollama_base_url)
    try:
        with urllib.request.urlopen(f"{url}/api/version", timeout=1.5):
            return True
    except OSError:
        return False


def _control_window(url: str, server: ServerThread) -> bool:
    """Janela pequena com o estado e botões. Devolve False se não houver interface gráfica."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return False
    try:
        root = tk.Tk()
    except tk.TclError:  # sem ambiente gráfico
        return False

    root.title(APP_NAME)
    root.geometry("380x230")
    root.resizable(False, False)
    root.configure(bg="#0f172a")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TButton", padding=(10, 6), font=("Segoe UI", 10))
    style.configure("Accent.TButton", foreground="white", background="#4f46e5")
    style.map("Accent.TButton", background=[("active", "#6366f1")])

    tk.Label(root, text="MultiMind", fg="white", bg="#0f172a", font=("Segoe UI", 18, "bold")).pack(
        pady=(18, 0)
    )
    tk.Label(
        root, text=f"A correr em {url}", fg="#a5b4fc", bg="#0f172a", font=("Segoe UI", 10)
    ).pack()
    ollama = tk.Label(root, text="", bg="#0f172a", font=("Segoe UI", 10))
    ollama.pack(pady=(6, 12))

    buttons = tk.Frame(root, bg="#0f172a")
    buttons.pack()
    ttk.Button(
        buttons,
        text="Abrir MultiMind",
        style="Accent.TButton",
        command=lambda: webbrowser.open(url),
    ).grid(row=0, column=0, padx=4)
    ttk.Button(buttons, text="Pasta de dados", command=lambda: _open_folder(DATA_DIR)).grid(
        row=0, column=1, padx=4
    )

    def quit_app() -> None:
        server.stop()
        root.destroy()

    ttk.Button(root, text="Sair", command=quit_app).pack(pady=12)
    root.protocol("WM_DELETE_WINDOW", quit_app)

    def refresh() -> None:
        running = _ollama_running()
        ollama.configure(
            text="● Ollama a correr" if running else "● Ollama desligado — abre a app Ollama",
            fg="#34d399" if running else "#fbbf24",
        )
        if server.is_alive():
            root.after(5000, refresh)
        else:
            root.destroy()

    refresh()
    root.mainloop()
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(argv)

    log_file = _prepare_io()
    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("multimind.desktop")

    # Uma só instância: se já houver um MultiMind nesta porta, só abre o browser.
    existing = _health(args.port)
    if existing and existing.get("app") == APP_NAME and not args.smoke_test:
        log.info("MultiMind já está aberto; a abrir o browser")
        webbrowser.open(f"http://127.0.0.1:{args.port}")
        return 0

    from app.core.config import get_settings
    from app.db.migrations import upgrade_to_head

    settings = get_settings()
    log.info("Pasta de dados: %s (executável: %s)", DATA_DIR, FROZEN)
    upgrade_to_head(settings.database_url)

    port = _choose_port(args.port)
    server = ServerThread(port)
    server.start()
    url = f"http://127.0.0.1:{port}"
    if not server.wait_ready():
        log.error("O servidor não arrancou; ver %s", log_file)
        return 1
    log.info("MultiMind pronto em %s", url)

    if args.smoke_test:
        with urllib.request.urlopen(f"{url}/", timeout=5) as r:
            page = r.read().decode(errors="replace")
        ok = _health(port) is not None and '<div id="root">' in page
        print("SMOKE TEST", "OK" if ok else "FALHOU", url, flush=True)
        server.stop()
        server.join(timeout=10)
        return 0 if ok else 1

    if not args.no_browser:
        webbrowser.open(url)
    if args.no_window or not _control_window(url, server):
        print(f"MultiMind a correr em {url} (Ctrl+C para sair)", flush=True)
        try:
            while server.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    server.stop()
    server.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
