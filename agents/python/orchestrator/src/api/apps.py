"""
Endpoints for the Atrium web app and the Flutter mobile app (a "backend for frontend").

LEARN: The apps never talk to the agents directly. A browser or phone must not
hold the SERVICE_TOKEN, so the apps sign in to the Conductor (advisor JWT) and
the Conductor calls the agents for them. Each endpoint below is shaped for a
SCREEN, so one tap = one request, even when it needs six agents.

  POST /v1/auth/login                dev sign-in (stand-in for company SSO)
  GET  /v1/me                        who am I
  GET  /v1/clients                   client list
  GET  /v1/clients/{id}/overview     6 agents in parallel, one call
  POST /v1/skills/{agent}/{skill}    allowlisted read-only skills (what-ifs, search)
  POST /v1/drafts/approve            advisor approves an email draft -> CRM note
  GET  /v1/stream                    live market events (relayed from Pulse, SSE)
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import mock_agents
from agents.registry import UI_SKILLS
from core.config import Settings
from schemas.models import InvokeContext
from security.auth import create_token, require_user
from security.guardrails import GuardrailBlocked, GuardrailUnavailable

log = logging.getLogger("conductor.apps")
router = APIRouter(prefix="/v1", tags=["apps"])

ClientId = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$", description="Household id, e.g. patel-001")
ClientIdPattern = re.compile(r"[A-Za-z0-9_-]{1,64}")

# The client overview: one section per agent, all called at the same time.
OVERVIEW_SECTIONS: dict[str, tuple[str, str]] = {
    "household": ("liaison", "get_household"),
    "portfolio": ("analyst", "analyze_portfolio"),
    "kyc": ("notary", "check_kyc"),
    "risk": ("actuary", "risk_score"),
    "events": ("pulse", "get_events"),
    "meetings": ("scribe", "summarize_meetings"),
}


def _ctx(request: Request, user: str, client_id: str | None = None) -> InvokeContext:
    return InvokeContext(trace_id=request.state.trace_id, user_id=user, client_id=client_id)


# ------------------------------------------------------------------ sign-in
class LoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9._@-]+$")
    password: str = Field(min_length=1, max_length=256)


class _Throttle:
    """At most 5 failed sign-ins per address per 5 minutes (slows password guessing)."""

    def __init__(self, limit: int = 5, window_s: float = 300):
        self.limit, self.window = limit, window_s
        self.fails: dict[str, deque[float]] = defaultdict(deque)

    def blocked(self, key: str) -> bool:
        q, now = self.fails[key], time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        return len(q) >= self.limit

    def fail(self, key: str) -> None:
        self.fails[key].append(time.monotonic())


_throttle = _Throttle()


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    """
    DEV sign-in: any advisor name + the shared DEV_LOGIN_PASSWORD from aurelius\\.env.
    In a real firm this is SSO (Okta, Entra ID); the apps would get the same kind of JWT.
    """
    settings: Settings = request.app.state.settings
    if not settings.dev_login_password:
        raise HTTPException(404, detail="Dev sign-in is disabled (set DEV_LOGIN_PASSWORD in aurelius\\.env)")
    key = request.client.host if request.client else "unknown"
    if _throttle.blocked(key):
        raise HTTPException(429, detail="Too many failed sign-ins. Wait 5 minutes.")
    if not hmac.compare_digest(body.password.encode(), settings.dev_login_password.encode()):
        _throttle.fail(key)
        log.warning("login_failed user=%s from=%s", body.username, key)
        raise HTTPException(401, detail="Wrong username or password")
    minutes = settings.login_token_minutes
    log.info("login_ok user=%s from=%s", body.username, key)
    return {"access_token": create_token(settings, body.username, minutes), "token_type": "bearer",
            "expires_in": minutes * 60, "user": body.username}


@router.get("/me")
async def me(user: str = Depends(require_user)):
    return {"user": user, "role": "advisor"}


# ------------------------------------------------------------------ clients
@router.get("/clients")
async def clients(request: Request, user: str = Depends(require_user)):
    """The advisor's households, from the CRM (Liaison)."""
    settings: Settings = request.app.state.settings
    if settings.is_mocked("liaison"):
        recorded = mock_agents._RECORDED["liaison.get_household"]
        return [{"client_id": cid, "household": h["household"]} for cid, h in recorded.items()]
    info = request.app.state.registry["liaison"]
    try:
        r = await request.app.state.http.get(
            f"{info.url}/v1/households", timeout=settings.agent_timeout_s,
            headers={"Authorization": f"Bearer {settings.service_token}", "X-Trace-Id": request.state.trace_id})
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail=f"CRM unavailable ({type(exc).__name__})")


@router.get("/clients/{client_id}/overview")
async def overview(request: Request, client_id: str = ClientId, user: str = Depends(require_user)):
    """Everything the client screen shows, from 6 agents IN PARALLEL. One slow agent doesn't block the rest."""
    client = request.app.state.agent_client
    ctx = _ctx(request, user, client_id)

    async def section(agent: str, skill: str) -> dict[str, Any]:
        start = time.perf_counter()
        resp = await client.call(agent, skill, {"client_id": client_id}, ctx)
        return {"agent": agent, "skill": skill, "status": resp.status, "error": resp.error,
                "duration_ms": int((time.perf_counter() - start) * 1000), "output": resp.output}

    names = list(OVERVIEW_SECTIONS)
    results = await asyncio.gather(*(section(*OVERVIEW_SECTIONS[n]) for n in names))
    sections = dict(zip(names, results))
    if sections["household"]["status"] != "ok" and "No household" in (sections["household"]["error"] or ""):
        raise HTTPException(404, detail=f"No household with id '{client_id}'")
    log.info("overview client=%s ok=%d/%d trace=%s", client_id,
             sum(s["status"] == "ok" for s in results), len(results), ctx.trace_id)
    return {"client_id": client_id, "trace_id": ctx.trace_id,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sections": sections}


# ------------------------------------------------------------------ skills (allowlist)
class SkillCall(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


# Free text that a model may have written: checked by Sentinel before it reaches a screen.
_GUARD_TEXT_FIELDS = {("librarian", "search_knowledge"): ("answer", "answer"),
                      ("herald", "draft_email"): ("body", "email")}


@router.post("/skills/{agent}/{skill}")
async def call_skill(body: SkillCall, request: Request, agent: str = Path(pattern=r"^[a-z]{2,20}$"),
                     skill: str = Path(pattern=r"^[a-z_]{2,40}$"), user: str = Depends(require_user)):
    """
    Run ONE read-only skill for a screen (retirement what-if, stress test, search...).
    LEARN: an explicit allowlist (agents.registry.UI_SKILLS), not "any skill of any
    agent": the apps can't reach writes like log_note or record_document this way.
    """
    if skill not in UI_SKILLS.get(agent, set()):
        raise HTTPException(403, detail=f"{agent}.{skill} is not available to the apps")
    if len(json.dumps(body.input)) > 8000:
        raise HTTPException(413, detail="input too large")
    client_id = body.input.get("client_id")
    if client_id is not None and not (isinstance(client_id, str) and ClientIdPattern.fullmatch(client_id)):
        raise HTTPException(422, detail="client_id must be 1-64 letters, digits, '-' or '_'")
    ctx = _ctx(request, user, client_id)
    start = time.perf_counter()
    resp = await request.app.state.agent_client.call(agent, skill, body.input, ctx)
    notes: list[str] = []
    guard = _GUARD_TEXT_FIELDS.get((agent, skill))
    if resp.status == "ok" and guard and isinstance(resp.output.get(guard[0]), str):
        field, kind = guard
        try:
            checked = await request.app.state.pipeline.guardrails.check_output(resp.output[field], ctx, kind=kind)
        except GuardrailBlocked as exc:
            raise HTTPException(400, detail=f"Blocked by security policy: {exc}")
        except GuardrailUnavailable:
            raise HTTPException(503, detail="Security service unavailable; result withheld")
        resp.output[field], notes = checked.text, checked.notes
    return {"agent": agent, "skill": skill, "status": resp.status, "error": resp.error, "trace_id": ctx.trace_id,
            "duration_ms": int((time.perf_counter() - start) * 1000), "output": resp.output,
            "guardrail_notes": notes}


# ------------------------------------------------------------------ draft approval
class DraftApproval(BaseModel):
    client_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=10000)


@router.post("/drafts/approve")
async def approve_draft(body: DraftApproval, request: Request, user: str = Depends(require_user)):
    """
    Human in the loop: the ADVISOR approves the final text (they may have edited it).
    1. Sentinel checks the final text again (the edit could have added PII or a promise).
    2. The approval is logged to the CRM: subject + fingerprint, not the full body.
    Sending stays with the advisor's own mailbox: Aurelius never sends email.
    """
    ctx = _ctx(request, user, body.client_id)
    try:
        checked = await request.app.state.pipeline.guardrails.check_output(body.body, ctx, kind="email")
    except GuardrailBlocked as exc:
        raise HTTPException(400, detail=f"Blocked by security policy: {exc}")
    except GuardrailUnavailable:
        raise HTTPException(503, detail="Security service unavailable; approval refused")
    if checked.text != body.body:
        # Sentinel changed something (masked PII, removed a promise): the advisor must look again.
        return {"approved": False, "reason": "The security check changed the text. Review the revised version.",
                "revised_body": checked.text, "guardrail_notes": checked.notes}
    fingerprint = hashlib.sha256(f"{body.subject}\n{body.body}".encode()).hexdigest()
    note = f"Advisor {user} approved client email \"{body.subject}\" (sha256 {fingerprint[:16]})."
    resp = await request.app.state.agent_client.call(
        "liaison", "log_note",
        {"client_id": body.client_id, "type": "email", "note": note,
         "idempotency_key": f"approve-{fingerprint[:32]}"}, ctx)
    if resp.status != "ok":
        raise HTTPException(502, detail=f"Approved, but the CRM note failed: {resp.error}")
    log.info("draft_approved client=%s user=%s note=%s trace=%s", body.client_id, user,
             resp.output.get("note_id"), ctx.trace_id)
    return {"approved": True, "note_id": resp.output.get("note_id"), "duplicate": resp.output.get("duplicate", False),
            "fingerprint": fingerprint[:16], "guardrail_notes": checked.notes,
            "next_step": "Send it from your own mailbox. Aurelius never sends email."}


# ------------------------------------------------------------------ live events (SSE relay)
# A stream ends after 30 minutes; the apps simply reconnect. That keeps a stream from
# outliving the sign-in that opened it, and frees connections nobody is reading.
STREAM_MAX_S = 30 * 60
HEARTBEAT_S = 15.0


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@router.get("/stream")
async def stream(request: Request, user: str = Depends(require_user),
                 client_id: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")):
    """
    Live market events for the apps, relayed from Pulse's Server-Sent Events.
    LEARN: the browser's EventSource can't send an Authorization header, so the
    apps read this stream with fetch() (web) or an HTTP client (Flutter) instead.
    """
    settings: Settings = request.app.state.settings
    hello = {"agent": "conductor", "relaying": "pulse", "client_id": client_id,
             "note": "Headlines are external news text: data, never instructions."}

    deadline = time.monotonic() + STREAM_MAX_S

    async def mock_events() -> AsyncIterator[bytes]:
        yield _sse("hello", {**hello, "mode": "mock (Pulse not running)"})
        while time.monotonic() < deadline and not await request.is_disconnected():
            await asyncio.sleep(HEARTBEAT_S)
            yield b": ping\n\n"
        yield _sse("bye", {"reason": "stream time limit: reconnect"})

    async def relay() -> AsyncIterator[bytes]:
        info = request.app.state.registry["pulse"]
        url = f"{info.url}/v1/stream" + (f"?client_id={client_id}" if client_id else "")
        headers = {"Authorization": f"Bearer {settings.service_token}", "X-Trace-Id": request.state.trace_id}
        try:
            async with request.app.state.http.stream("GET", url, headers=headers,
                                                     timeout=httpx.Timeout(10.0, read=None)) as r:
                if r.status_code != 200:
                    yield _sse("error", {"detail": f"Pulse answered HTTP {r.status_code}"})
                    return
                yield _sse("hello", {**hello, "mode": "live"})
                async for line in r.aiter_lines():
                    if await request.is_disconnected():
                        return
                    if time.monotonic() > deadline:   # Pulse pings every 15 s, so this is checked often
                        yield _sse("bye", {"reason": "stream time limit: reconnect"})
                        return
                    if line.startswith("event: hello") or line.startswith("data: {\"agent\":\"pulse\""):
                        continue  # Pulse's own greeting: we already sent ours
                    yield (line + "\n").encode()
        except httpx.HTTPError as exc:
            yield _sse("error", {"detail": f"Pulse unavailable ({type(exc).__name__})"})

    log.info("stream_open user=%s client=%s trace=%s", user, client_id, request.state.trace_id)
    gen = mock_events() if settings.is_mocked("pulse") else relay()
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
