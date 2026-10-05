"""Part 1: shared agent contract. Part 2: the Analyst's skills."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================ agent contract


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


# ============================================================ skill inputs
ClientIdField = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Client household id, e.g. patel-001")


class AnalyzeInput(BaseModel):
    client_id: str = ClientIdField


class AskInput(BaseModel):
    client_id: str = ClientIdField
    question: str = Field(min_length=3, max_length=1000)


# ============================================================ analyze_portfolio output
class AllocationCheck(BaseModel):
    target_pct: dict[str, float]
    current_pct: dict[str, float]
    drift_pts: dict[str, float] = Field(description="current minus target, in percentage points")
    needs_rebalance: bool
    flags: list[str]


class ConcentrationFlag(BaseModel):
    symbol: str
    name: str
    weight_pct: float
    level: Literal["review", "escalate"]
    message: str


class TaxLossIdea(BaseModel):
    symbol: str
    name: str
    account_id: str
    unrealized_loss: float
    replacements: list[str]
    wash_sale_risk: bool
    note: str


class AnalysisResult(BaseModel):
    client_id: str
    household: str
    as_of: str
    total_value: float
    allocation: AllocationCheck
    concentration: list[ConcentrationFlag]
    tax_loss_ideas: list[TaxLossIdea]
    actions: list[str] = Field(description="Suggested next steps for the advisor")
    summary: str
    answered_by: str = Field(description="Claude model, or 'template' without an API key")
    mcp_tools_used: list[str]


class AskResult(BaseModel):
    answer: str
    tool_calls: list[dict[str, Any]]
    turns: int
    answered_by: str
