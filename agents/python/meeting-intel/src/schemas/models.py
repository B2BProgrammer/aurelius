"""
Part 1: shared agent contract. Part 2: what the Scribe extracts from a meeting.

LEARN: MeetingExtract is the SCHEMA for structured extraction. It's used
three ways:
  1. as the JSON schema Claude must fill in (forced tool call)
  2. to VALIDATE what Claude returns (bad output is rejected, not trusted)
  3. as the shape the rule-based fallback produces
One model, so the LLM path and the no-LLM path always return the same shape.
"""
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


# ============================================================ extraction schema
class ActionItem(BaseModel):
    owner: Literal["advisor", "client", "unknown"] = Field(description="Who must do it")
    task: str = Field(max_length=300, description="What must be done, as a short imperative sentence")
    due: str | None = Field(default=None, description="Due date as YYYY-MM-DD if stated, else null")


class ComplianceFlag(BaseModel):
    type: Literal["complaint", "client_trade_request", "concentration_increase",
                  "pii_in_notes", "other"]
    detail: str = Field(max_length=300)


class MeetingExtract(BaseModel):
    summary: str = Field(max_length=800, description="2-3 sentence factual summary of the meeting")
    action_items: list[ActionItem] = Field(default_factory=list)
    client_concerns: list[str] = Field(default_factory=list, description="Worries the clients expressed")
    life_events: list[str] = Field(default_factory=list,
                                   description="Retirement, weddings, births, college, home purchase, etc.")
    compliance_flags: list[ComplianceFlag] = Field(default_factory=list)
    next_meeting: str | None = Field(default=None, description="When the next meeting is, if stated")


# ============================================================ skill inputs / outputs
ClientId = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Client household id, e.g. patel-001")


class SummarizeInput(BaseModel):
    client_id: str = ClientId
    last_n: int | None = Field(default=None, ge=1, le=10, description="How many recent meetings to read")


class ExtractInput(BaseModel):
    notes: str = Field(min_length=20, description="Raw meeting notes or transcript text")
    meeting_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    client_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class MeetingResult(BaseModel):
    date: str | None
    type: str | None = None
    source: str | None = None
    extract: MeetingExtract
    extracted_by: str = Field(description="Claude model, or 'rules' without an API key")
    pii_masked: list[str] = Field(default_factory=list, description="PII types removed before the LLM saw the text")


class SummarizeResult(BaseModel):
    client_id: str
    meetings_found: int
    last_meeting: str | None
    summary: str = Field(description="Summary of the most recent meeting")
    open_action_items: list[ActionItem]
    client_concerns: list[str]
    life_events: list[str]
    compliance_flags: list[ComplianceFlag]
    meetings: list[MeetingResult]
