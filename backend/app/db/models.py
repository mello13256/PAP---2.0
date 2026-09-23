"""Importa todos os modelos para que fiquem registados em ``Base.metadata``.

Usado pelo Alembic (migrações) e pelos testes (criação das tabelas).
"""

from app.agents.models import Agent
from app.auth.models import User
from app.db.base import Base
from app.decisions.models import Decision, DecisionProposal
from app.experiments.models import Experiment
from app.interventions.models import Intervention
from app.messages.models import Message
from app.metrics.models import LLMCall, RunMetrics
from app.projects.models import Project
from app.reviews.models import Review, ReviewIssue
from app.runs.models import Run, RunEvent
from app.tasks.models import Task, task_dependencies
from app.workspace.models import Artifact, ArtifactVersion

__all__ = [
    "Agent",
    "Artifact",
    "ArtifactVersion",
    "Base",
    "Decision",
    "DecisionProposal",
    "Experiment",
    "Intervention",
    "LLMCall",
    "Message",
    "Project",
    "Review",
    "ReviewIssue",
    "Run",
    "RunEvent",
    "RunMetrics",
    "Task",
    "User",
    "task_dependencies",
]
