"""`python -m app.cli run "objetivo"`: corre o MultiMind no terminal, em tempo real.

Usa exatamente o mesmo motor que a API (orquestrador, BD, workspace); apenas
mostra os eventos no terminal em vez de os enviar para o browser.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets

from sqlalchemy import select

from app.agents import service as agents_service
from app.auth.models import User
from app.auth.security import hash_password
from app.core.config import get_settings
from app.db.migrations import upgrade_to_head
from app.main import create_app
from app.projects.models import Project
from app.runs import service as runs_service
from app.runs.schemas import RunCreate

if os.name == "nt":
    os.system("")  # ativa cores ANSI na consola do Windows

C = {
    "dim": "\033[2m",
    "bold": "\033[1m",
    "reset": "\033[0m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}
AGENT_COLORS = ["cyan", "magenta", "yellow", "blue", "green"]


def paint(text: str, *styles: str) -> str:
    return "".join(C[s] for s in styles) + text + C["reset"]


async def _user(session, email: str | None) -> User:
    if email:
        user = await session.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            raise SystemExit(f"Não existe nenhuma conta com o email {email}")
        return user
    users = list(await session.scalars(select(User)))
    if len(users) == 1:
        return users[0]
    if len(users) > 1:
        emails = ", ".join(u.email for u in users)
        raise SystemExit(f"Há várias contas; indica uma com --email ({emails})")
    user = User(
        email="cli@multimind.local",
        display_name="CLI",
        password_hash=hash_password(secrets.token_urlsafe(16)),
    )
    session.add(user)
    await session.commit()
    await agents_service.create_default_agents(session, user)
    return user


async def _project(session, user: User, name: str) -> Project:
    project = await session.scalar(
        select(Project).where(Project.owner_id == user.id, Project.name == name)
    )
    if project is None:
        project = Project(owner_id=user.id, name=name, description="Criado pelo CLI")
        session.add(project)
        await session.commit()
    return project


def _printer(names: dict[str, str]):
    colors = {agent_id: AGENT_COLORS[i % len(AGENT_COLORS)] for i, agent_id in enumerate(names)}
    state = {"streaming": False}

    def newline() -> None:
        if state["streaming"]:
            print()
            state["streaming"] = False

    def show(event) -> bool:
        p = event.payload
        kind = event.type
        if kind == "agent.started":
            newline()
            label = f" · {p['label']}" if p.get("label") else ""
            color = colors.get(p["agent_id"], "cyan")
            print(paint(f"\n[{p['agent_name']}{label}]", "bold", color))
        elif kind == "agent.delta":
            print(p["text"], end="", flush=True)
            state["streaming"] = True
        elif kind == "tool.called":
            newline()
            args = p.get("arguments", {})
            target = args.get("path") or args.get("to") or ""
            mark = paint("✓", "green") if p["ok"] else paint("✗", "red")
            print(
                paint(f"  → {p['name']}({target}) ", "dim") + mark + paint(f" {p['output']}", "dim")
            )
        elif kind == "task.updated":
            newline()
            who = names.get(p.get("assigned_agent_id") or "", "")
            print(
                paint(f"■ {p['key']} {p['title']} → {p['status']}", "bold")
                + (paint(f"  ({who})", "dim") if who else "")
            )
        elif kind == "message.created" and p["kind"] in ("ORCHESTRATOR", "SYSTEM", "REVIEW"):
            newline()
            color = {"ORCHESTRATOR": "blue", "SYSTEM": "red", "REVIEW": "yellow"}[p["kind"]]
            print(paint(f"[{p['kind']}] ", "bold", color) + p["content"])
        elif kind == "run.status":
            newline()
            print(paint(f"=== run: {p['status']} ===", "bold"))
        elif kind == "run.finished":
            newline()
            return True
        return False

    return show


async def run_cli(
    objective: str, strategy: str, email: str | None, project_name: str, agent_names: list[str]
) -> int:
    settings = get_settings()
    logging.getLogger().setLevel(logging.WARNING)
    app = create_app(settings)
    logging.getLogger().setLevel(logging.WARNING)
    state = app.state
    try:
        async with state.db.sessionmaker() as session:
            user = await _user(session, email)
            project = await _project(session, user, project_name)
            agents = await agents_service.list_agents(session, user)
            by_name = {a.name.lower(): a for a in agents}
            chosen = []
            for name in agent_names:
                if name.lower() not in by_name:
                    raise SystemExit(
                        f"Agente desconhecido: {name} ({', '.join(a.name for a in agents)})"
                    )
                chosen.append(by_name[name.lower()].id)
            run = await runs_service.create_run(
                session,
                state.bus,
                project,
                user,
                RunCreate(objective=objective, strategy_key=strategy, agent_ids=chosen),
            )
            names = {str(a.id): a.name for a in agents}

        print(paint("MultiMind", "bold") + f" · estratégia {strategy} · projeto «{project.name}»")
        print(paint(f"Objetivo: {objective}\n", "dim"))
        show = _printer(names)
        with state.bus.subscribe(run.id) as sub:
            await state.run_manager.start(run.id)
            try:
                while True:
                    event = await sub.queue.get()
                    if show(event):
                        break
            except (KeyboardInterrupt, asyncio.CancelledError):
                print(paint("\nA cancelar...", "red"))
                await state.run_manager.cancel(run.id)
                raise

        async with state.db.sessionmaker() as session:
            from app.metrics.service import compute_run_metrics
            from app.runs.models import Run

            final = await session.get(Run, run.id)
            metrics = await compute_run_metrics(session, run.id)
        print(
            paint(f"\nEstado final: {final.status}", "bold")
            + (f" — {final.failure_reason}" if final.failure_reason else "")
        )
        print(
            paint(
                f"{metrics.api_calls} chamadas · "
                f"{metrics.input_tokens}→{metrics.output_tokens} tokens · "
                f"{metrics.tasks_completed}/{metrics.tasks_total} tarefas · "
                f"{metrics.reviews} revisões "
                f"({metrics.revisions} pedidos de correção) · {metrics.execution_time_s:.0f}s",
                "dim",
            )
        )
        folder = (settings.workspaces_dir / str(project.id)).resolve()
        print(paint(f"Ficheiros produzidos: {folder}", "green"))
        print(paint(f"Run: {run.id}", "dim"))
        return 0 if str(final.status) == "COMPLETED" else 1
    finally:
        await state.background.cancel_all()
        await state.db.dispose()


def main(argv) -> int:
    settings = get_settings()
    upgrade_to_head(settings.database_url)
    try:
        return asyncio.run(
            run_cli(
                argv.objective,
                argv.strategy,
                argv.email,
                argv.project,
                [n for n in (argv.agents or "").split(",") if n.strip()],
            )
        )
    except KeyboardInterrupt:
        return 130
