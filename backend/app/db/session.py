"""Ligação à base de dados.

Uma instância de ``Database`` é criada por aplicação (ver ``main.create_app``) e
guardada em ``app.state.db``. Cada pedido HTTP recebe a sua própria sessão.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _configure_sqlite(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        # WAL: leitores não bloqueiam o escritor (o orquestrador escreve enquanto a UI lê).
        cursor.execute("PRAGMA journal_mode=WAL")
        # Em SQLite as chaves estrangeiras estão DESLIGADAS por defeito.
        cursor.execute("PRAGMA foreign_keys=ON")
        # Se a BD estiver ocupada, espera até 5 s em vez de falhar logo.
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


class Database:
    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = create_async_engine(url, echo=echo)
        if self.engine.dialect.name == "sqlite":
            _configure_sqlite(self.engine)
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Dependência FastAPI: uma sessão por pedido, fechada no fim."""
    db: Database = request.app.state.db
    async with db.sessionmaker() as session:
        yield session
