"""
Fake agents for learning and testing (MOCK_AGENTS=true).

LEARN: A "test double": when MOCK_AGENTS=true (or an agent isn't in
REAL_AGENTS), the Conductor answers for that agent itself, with the agent's
real recorded output. Switch MOCK_AGENTS=false and nothing else changes.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
from pathlib import Path
from typing import Any

from schemas.models import AgentRequest, AgentResponse

# --- Sentinel's checks (a simple version of what the real Sentinel will do) ---
_PII_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ACCOUNT_NUMBER": re.compile(r"\b\d{8,12}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "PHONE": re.compile(r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
}
_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"reveal (your|the) (system prompt|instructions)",
    r"you are now (in )?(developer|dan|jailbreak)",
]


def mask_pii(text: str) -> tuple[str, list[str]]:
    found = []
    for label, pattern in _PII_PATTERNS.items():
        if pattern.search(text):
            found.append(label)
            text = pattern.sub(f"[{label}]", text)
    return text, found


def _sentinel(req: AgentRequest) -> dict[str, Any]:
    text = str(req.input.get("text", ""))
    masked, found = mask_pii(text)
    notes = [f"Masked {label}" for label in found]
    if req.skill == "guard_input":
        lowered = text.lower()
        if any(re.search(p, lowered) for p in _INJECTION_PATTERNS):
            return {"allowed": False, "text": "", "notes": ["Blocked: possible prompt injection"]}
        return {"allowed": True, "text": masked, "notes": notes}
    # guard_output: the advisor-facing answer gets a disclosure, client emails don't
    if req.input.get("kind", "answer") != "answer":
        return {"allowed": True, "text": masked, "notes": notes}
    disclosure = ("\n\n_For advisor use only. Not investment advice to clients until "
                  "reviewed. Projections are hypothetical and not guaranteed._")
    return {"allowed": True, "text": masked + disclosure, "notes": notes + ["Added disclosure"]}


# --- Recorded answers from the REAL agents -------------------------------------
# LEARN: these are not made up. recorded_responses.json holds the actual output
# each real agent returned for the three demo households, so code written against
# the mocks (the Conductor, the web and mobile apps) works unchanged against the
# real agents. Re-record whenever an agent's output shape changes.
_RECORDED: dict[str, dict[str, Any]] = json.loads(
    (Path(__file__).with_name("recorded_responses.json")).read_text(encoding="utf-8"))["responses"]


def _recorded(agent: str, req: AgentRequest) -> AgentResponse:
    per_client = _RECORDED.get(f"{agent}.{req.skill}")
    if per_client is None:
        return AgentResponse(agent=agent, status="error", error=f"mock has no skill {req.skill}")
    if "*" in per_client:  # skills without a client (scan, search...)
        return AgentResponse(agent=agent, status="ok", output=copy.deepcopy(per_client["*"]))
    client_id = req.input.get("client_id") or req.context.client_id
    if client_id not in per_client:  # behave like the real agents: unknown client = error
        return AgentResponse(agent=agent, status="error", error=f"No household with id '{client_id}'")
    return AgentResponse(agent=agent, status="ok", output=copy.deepcopy(per_client[client_id]))


def _write(agent: str, req: AgentRequest) -> AgentResponse | None:
    """Writes are never recorded (they change data); answer like the real agent would."""
    if (agent, req.skill) == ("liaison", "log_note"):
        return AgentResponse(agent=agent, status="ok",
                             output={"note_id": "N-MOCK-1", "duplicate": False, "pii_masked": []})
    return None


async def respond(agent: str, req: AgentRequest) -> AgentResponse:
    await asyncio.sleep(0.05)  # pretend network latency so parallelism is visible
    if agent == "sentinel":
        return AgentResponse(agent=agent, status="ok", output=_sentinel(req))
    return _write(agent, req) or _recorded(agent, req)
