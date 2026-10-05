"""
Data models.

Part 1 is the shared AGENT CONTRACT (identical shape in every agent).
Part 2 is what Sentinel's two skills accept and return.

LEARN: The contract is copied into each agent for now. Later you can
generate it for every language from one JSON Schema in aurelius\\contracts\\.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Part 1: agent contract
# =============================================================================
class InvokeContext(BaseModel):
    trace_id: str
    user_id: str
    client_id: str | None = None


class AgentRequest(BaseModel):
    skill: str
    input: dict[str, Any] = Field(default_factory=dict)
    context: InvokeContext


class AgentResponse(BaseModel):
    agent: str
    status: Literal["ok", "error"]
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


# =============================================================================
# Part 2: Sentinel skills
# =============================================================================
TextKind = Literal["request", "answer", "email"]


class GuardInput(BaseModel):
    """Input for both guard_input and guard_output."""

    text: str = Field(description="The text to check")
    kind: TextKind = Field(
        default="answer",
        description="request = advisor's message, answer = briefing for the advisor, "
                    "email = draft that may go to a client",
    )


class Finding(BaseModel):
    rule: str = Field(description="Which rule fired, e.g. PII_SSN or INJ_OVERRIDE")
    category: Literal["pii", "injection", "compliance", "secret"]
    count: int = 1


class GuardResult(BaseModel):
    """What both skills return. The Conductor reads allowed, text and notes."""

    allowed: bool = Field(description="false = refuse the whole request")
    decision: Literal["allow", "sanitized", "block"]
    text: str = Field(description="Safe version of the text (PII masked, fixes applied)")
    notes: list[str] = Field(default_factory=list, description="Human-readable explanation")
    findings: list[Finding] = Field(default_factory=list)
    injection_score: float = 0.0
    llm_checked: bool = False
