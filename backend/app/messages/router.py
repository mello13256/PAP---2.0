from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.agents import service as agents_service
from app.auth.dependencies import CurrentUser, SessionDep
from app.core.errors import InvalidStateError
from app.messages import service
from app.messages.models import MessageKind
from app.messages.schemas import AskAgentRequest, MessageOut, UserMessageCreate
from app.orchestration.conversation import agent_turn
from app.runs.dependencies import OwnedRun

router = APIRouter(tags=["messages"])


@router.get("/runs/{run_id}/messages", response_model=list[MessageOut])
async def list_messages(run: OwnedRun, session: SessionDep) -> list[MessageOut]:
    return [MessageOut.model_validate(m) for m in await service.list_messages(session, run.id)]


@router.post(
    "/runs/{run_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
async def post_user_message(
    data: UserMessageCreate, run: OwnedRun, user: CurrentUser, session: SessionDep, request: Request
) -> MessageOut:
    if data.recipient_agent_id is not None:
        await agents_service.get_agent(session, user, data.recipient_agent_id)
    message = await service.post_message(
        session,
        request.app.state.bus,
        run_id=run.id,
        kind=MessageKind.USER,
        content=data.content,
        sender_user_id=user.id,
        recipient_agent_id=data.recipient_agent_id,
    )
    return MessageOut.model_validate(message)


@router.post("/runs/{run_id}/ask", status_code=status.HTTP_202_ACCEPTED)
async def ask_agent(
    data: AskAgentRequest, run: OwnedRun, user: CurrentUser, session: SessionDep, request: Request
) -> dict:
    """Dá a palavra a um agente. A resposta chega pelos eventos do run (SSE).

    Se ``prompt`` vier preenchido, é guardado primeiro como mensagem do utilizador
    dirigida a esse agente.
    """
    agent = await agents_service.get_agent(session, user, data.agent_id)
    if not agent.enabled:
        raise InvalidStateError(f"O agente {agent.name} está desativado")
    state = request.app.state
    if data.prompt:
        await service.post_message(
            session,
            state.bus,
            run_id=run.id,
            kind=MessageKind.USER,
            content=data.prompt,
            sender_user_id=user.id,
            recipient_agent_id=agent.id,
        )
    names = {a.id: a.name for a in await agents_service.list_agents(session, user)}
    state.background.spawn(
        agent_turn(
            sessionmaker=state.db.sessionmaker,
            bus=state.bus,
            factory=state.runtime_factory,
            run_id=run.id,
            agent_id=agent.id,
            agent_names=names,
        ),
        name=f"agent-turn:{agent.name}",
    )
    return {"status": "accepted", "agent_id": str(agent.id)}
