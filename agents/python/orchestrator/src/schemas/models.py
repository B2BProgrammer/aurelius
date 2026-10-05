"""
Data models.

LEARN: Part 1 is the shared AGENT CONTRACT. Every agent in the swarm, whether
it is written in Python, Node, Java or Go, accepts AgentRequest at
POST /invoke and returns AgentResponse. Because they all speak the same JSON,
the Conductor can call any of them the same way.

Part 2 is the Conductor's own API for the React frontend (Atrium).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Part 1: the agent contract (same JSON shape for all 10 agents)
# =============================================================================
class InvokeContext(BaseModel):
    trace_id: str = Field(description="Follows one advisor request across every agent's logs")
    user_id: str = Field(description="The advisor making the request")
    client_id: str | None = Field(default=None, description="The client household, if any")


class AgentRequest(BaseModel):
    skill: str = Field(description="Which capability of the agent to run, e.g. 'draft_email'")
    input: dict[str, Any] = Field(default_factory=dict)
    context: InvokeContext


class AgentResponse(BaseModel):
    agent: str
    status: Literal["ok", "error"]
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# =============================================================================
# Part 2: planning and results
# =============================================================================
class PlanStep(BaseModel):
    agent: str
    skill: str
    input: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class Plan(BaseModel):
    """Stages run one after another; the steps inside a stage run in parallel."""

    stages: list[list[PlanStep]] = Field(default_factory=list)
    source: Literal["llm", "rules"] = "llm"


class StepResult(BaseModel):
    agent: str
    skill: str
    status: Literal["ok", "error"]
    duration_ms: int
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# =============================================================================
# Part 3: the API the React frontend calls
# =============================================================================
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    # Only letters, digits, _ and - : stops odd input reaching downstream systems
    client_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class Draft(BaseModel):
    """Something the advisor must approve before it is used (human in the loop)."""

    kind: str
    content: dict[str, Any]
    requires_approval: bool = True


class ChatResponse(BaseModel):
    trace_id: str
    answer: str
    plan: Plan
    steps: list[StepResult]
    drafts: list[Draft] = Field(default_factory=list)
    guardrail_notes: list[str] = Field(default_factory=list)
