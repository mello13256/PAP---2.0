"""As migrações Alembic produzem exatamente o esquema definido nos modelos."""

import asyncio

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db.migrations import upgrade_to_head
from app.db.models import Base


def test_migrations_match_models(tmp_path) -> None:
    db_file = (tmp_path / "migrated.db").as_posix()
    upgrade_to_head(f"sqlite+aiosqlite:///{db_file}")

    engine = create_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_upgrade_can_run_from_inside_an_event_loop(tmp_path) -> None:
    # Reproduz o que a app faz no arranque (asyncio.to_thread dentro de um loop).
    db_file = (tmp_path / "loop.db").as_posix()

    async def main() -> None:
        await asyncio.to_thread(upgrade_to_head, f"sqlite+aiosqlite:///{db_file}")

    asyncio.run(main())
