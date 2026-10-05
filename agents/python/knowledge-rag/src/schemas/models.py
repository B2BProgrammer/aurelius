"""
Part 1: the shared agent contract (same in every agent).
Part 2: what the Librarian's skill accepts and returns.
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


# ============================================================ Librarian
DocType = Literal["policy", "guide", "research", "product", "external"]


class SearchInput(BaseModel):
    query: str = Field(min_length=1, description="The question to answer from firm documents")
    top_k: int | None = Field(default=None, ge=1, le=10, description="How many passages to use")
    doc_type: DocType | None = Field(default=None, description="Only search one kind of document")


class Citation(BaseModel):
    ref: int = Field(description="The [n] number used in the answer")
    title: str
    source: str = Field(description="File name of the document")
    section: str
    effective_date: str
    score: float = Field(description="Similarity 0..1 (higher = closer match)")
    snippet: str


class SearchResult(BaseModel):
    answer: str
    grounded: bool = Field(description="false = the documents did not contain the answer")
    citations: list[Citation] = Field(default_factory=list)
    passages_considered: int = 0
    answered_by: str = Field(description="The Claude model, or 'extractive' without an API key")


class IngestReport(BaseModel):
    documents: int
    chunks: int
    quarantined: list[dict[str, str]] = Field(default_factory=list)
    removed_sources: list[str] = Field(default_factory=list)
    embedding_provider: str
    duration_ms: int
