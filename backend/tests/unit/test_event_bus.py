import uuid

from sqlalchemy import select

from app.events.bus import EventBus
from app.events.sse import event_stream, format_sse
from app.runs.models import RunEvent


async def _new_run(app) -> uuid.UUID:
    from app.auth.models import User
    from app.projects.models import Project
    from app.runs.models import Run

    async with app.state.db.sessionmaker() as session:
        user = User(email=f"{uuid.uuid4()}@x.com", display_name="x", password_hash="x")
        session.add(user)
        await session.flush()
        project = Project(owner_id=user.id, name="p")
        session.add(project)
        await session.flush()
        run = Run(project_id=project.id, objective="o", strategy_key="s")
        session.add(run)
        await session.commit()
        return run.id


async def test_persistent_events_get_sequential_ids_and_are_stored(app) -> None:
    run_id = await _new_run(app)
    bus: EventBus = app.state.bus
    first = await bus.publish(run_id, "a", {"x": uuid.UUID(int=1)})
    second = await bus.publish(run_id, "b")
    assert first.id is not None and second.id == first.id + 1
    assert first.payload == {"x": "00000000-0000-0000-0000-000000000001"}  # JSON-friendly

    async with app.state.db.sessionmaker() as session:
        types = [e.type for e in await session.scalars(select(RunEvent).order_by(RunEvent.id))]
    assert types == ["a", "b"]


async def test_transient_events_are_delivered_but_not_stored(app) -> None:
    run_id = await _new_run(app)
    bus: EventBus = app.state.bus
    with bus.subscribe(run_id) as sub:
        event = await bus.publish(run_id, "agent.delta", {"text": "Ol"}, persist=False)
        assert event.id is None
        assert (await sub.queue.get()).payload == {"text": "Ol"}
    assert bus.subscriber_count(run_id) == 0

    async with app.state.db.sessionmaker() as session:
        assert list(await session.scalars(select(RunEvent))) == []


async def test_events_only_go_to_subscribers_of_that_run(app) -> None:
    run_a, run_b = await _new_run(app), await _new_run(app)
    bus: EventBus = app.state.bus
    with bus.subscribe(run_a) as sub_a:
        await bus.publish(run_b, "x", persist=False)
        assert sub_a.queue.empty()


async def test_slow_subscriber_is_cut_off(app, monkeypatch) -> None:
    import asyncio

    run_id = await _new_run(app)
    bus: EventBus = app.state.bus
    with bus.subscribe(run_id) as sub:
        sub.queue = asyncio.Queue(maxsize=1)
        await bus.publish(run_id, "1", persist=False)
        await bus.publish(run_id, "2", persist=False)
        assert sub.overflowed


async def test_stream_replays_stored_events_after_last_id(app) -> None:
    run_id = await _new_run(app)
    bus: EventBus = app.state.bus
    first = await bus.publish(run_id, "one")
    await bus.publish(run_id, "two")

    chunks = [
        c
        async for c in event_stream(
            bus, app.state.db.sessionmaker, run_id, last_event_id=first.id, follow=False
        )
    ]
    assert len(chunks) == 1
    assert "event: two" in chunks[0]


def test_sse_format() -> None:
    from datetime import UTC, datetime

    from app.events.bus import Event

    event = Event(uuid.uuid4(), "message.created", {"content": "olá"}, datetime.now(UTC), id=7)
    text = format_sse(event)
    assert text.startswith("id: 7\nevent: message.created\ndata: {")
    assert '"content": "olá"' in text
    assert text.endswith("\n\n")
