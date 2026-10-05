"""
Scribe HTTP API.

Endpoints
  GET  /health                     liveness (no auth)
  GET  /.well-known/agent.json     agent card with schemas (no auth)
  POST /invoke                     summarize_meetings | extract_meeting (service token)
  GET  /v1/meetings/{client_id}    which stored meetings exist for a client (service token)

Started by src/main.py.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from core.config import VERSION, Settings, get_settings
from extract.service import Scribe
from notes.store import CLIENT_ID, NotesStore
from schemas.models import (AgentRequest, AgentResponse, ExtractInput, MeetingResult, SummarizeInput,
                            SummarizeResult)
from security.auth import check_startup_security, require_service

log = logging.getLogger("scribe.api")

SKILLS = {
    "summarize_meetings": ("Summarize a client's recent stored meeting notes: latest summary, action items, "
                           "concerns, life events and compliance flags.", SummarizeInput, SummarizeResult),
    "extract_meeting": ("Turn raw meeting notes or a transcript (pasted text) into a structured record.",
                        ExtractInput, MeetingResult),
}


def create_app(settings: Settings | None = None, llm_client: Any = None) -> FastAPI:
    settings = settings or get_settings()
    check_startup_security(settings)
    store = NotesStore(settings.notes_dir)

    app = FastAPI(title="Aurelius Scribe (meeting-intel)", version=VERSION)
    app.state.settings = settings
    app.state.scribe = Scribe(settings, store, llm_client)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        request.state.trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        trace = getattr(request.state, "trace_id", "unknown")
        log.exception("unhandled_error trace=%s", trace)
        return JSONResponse(status_code=500, content={"detail": "Internal error", "trace_id": trace})

    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "scribe", "version": VERSION,
                "clients_with_notes": len(store.clients()),
                "extraction": settings.llm_model if app.state.scribe.llm else "rules"}

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": "scribe", "codename": "Scribe", "folder": "meeting-intel", "language": "Python",
            "version": VERSION,
            "description": "Meeting intelligence: summaries, action items, concerns, life events, compliance flags.",
            "auth": "Bearer SERVICE_TOKEN",
            "endpoints": {"invoke": "/invoke", "meetings": "/v1/meetings/{client_id}"},
            "skills": {n: {"description": d, "input_schema": i.model_json_schema(),
                           "output_schema": o.model_json_schema()} for n, (d, i, o) in SKILLS.items()},
        }

    @app.get("/v1/meetings/{client_id}")
    async def list_meetings(client_id: str, _: str = Depends(require_service)):
        if not CLIENT_ID.match(client_id):
            return JSONResponse(status_code=422, content={"detail": "invalid client_id"})
        return {"client_id": client_id,
                "meetings": [{"date": m.date, "type": m.type, "source": m.source, "chars": len(m.text)}
                             for m in store.meetings(client_id, 50)]}

    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(body: AgentRequest, request: Request, _: str = Depends(require_service)):
        start = time.perf_counter()
        if body.skill not in SKILLS:
            return AgentResponse(agent="scribe", status="error", error=f"unknown skill {body.skill}")
        model = SKILLS[body.skill][1]
        data = {k: v for k, v in body.input.items() if k in model.model_fields}
        if body.skill == "summarize_meetings":
            data.setdefault("client_id", body.context.client_id)
        try:
            params = model.model_validate(data)
        except ValidationError as exc:
            err = exc.errors()[0]
            return AgentResponse(agent="scribe", status="error",
                                 error=f"invalid input: {err['loc'][0] if err['loc'] else ''} {err['msg']}")

        scribe: Scribe = request.app.state.scribe
        if body.skill == "summarize_meetings":
            result: SummarizeResult | MeetingResult = await scribe.summarize(params.client_id, params.last_n)
        else:
            if len(params.notes) > settings.max_notes_chars:
                return AgentResponse(agent="scribe", status="error",
                                     error=f"notes longer than {settings.max_notes_chars} characters")
            result = await scribe.extract_one(params.notes, params.meeting_date, None, source="pasted")

        log.info("invoke skill=%s ms=%d trace=%s", body.skill, (time.perf_counter() - start) * 1000,
                 body.context.trace_id)
        return AgentResponse(agent="scribe", status="ok", output=result.model_dump())

    return app
