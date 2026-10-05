"""
Sentinel HTTP API.

Endpoints
  GET  /health                  liveness check (no auth)
  GET  /.well-known/agent.json  agent card: skills + input/output JSON schemas (no auth)
  POST /invoke                  the agent contract: guard_input / guard_output (service token)
  GET  /v1/rules                every active rule and what it catches (service token)

Started by src/main.py.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from audit.audit_log import AuditLog
from core.config import VERSION, Settings, get_settings
from guards.compliance import PROMISSORY_RULES
from guards.engine import GuardEngine
from guards.injection import INJECTION_RULES
from guards.pii import PII_RULES, SECRET_RULES
from llm.classifier import Classifier, build_classifier
from schemas.models import AgentRequest, AgentResponse, GuardInput, GuardResult
from security.auth import check_startup_security, require_service

log = logging.getLogger("sentinel.api")

SKILLS = {
    "guard_input": "Check an advisor's request before any LLM sees it: mask PII and secrets, "
                   "block prompt injection.",
    "guard_output": "Check an answer or client email before a person sees it: mask leaked PII, "
                    "remove non-compliant claims, add required disclosures.",
}


def create_app(settings: Settings | None = None, classifier: Classifier | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_startup_security(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = GuardEngine(settings, classifier or build_classifier(settings))
        app.state.audit = AuditLog(settings.audit_path)
        log.info("sentinel_started port=%s llm_classifier=%s audit=%s",
                 settings.port, settings.use_llm and classifier is None, settings.audit_path)
        yield

    app = FastAPI(title="Aurelius Sentinel (compliance-guard)", version=VERSION, lifespan=lifespan)
    app.state.settings = settings

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

    # ------------------------------------------------------------------ routes
    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": "sentinel", "version": VERSION}

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": "sentinel",
            "codename": "Sentinel",
            "folder": "compliance-guard",
            "language": "Python",
            "version": VERSION,
            "description": "Security and compliance guardrails for every request and answer.",
            "auth": "Bearer SERVICE_TOKEN",
            "endpoints": {"invoke": "/invoke", "rules": "/v1/rules"},
            "skills": {
                name: {"description": desc,
                       "input_schema": GuardInput.model_json_schema(),
                       "output_schema": GuardResult.model_json_schema()}
                for name, desc in SKILLS.items()
            },
        }

    @app.get("/v1/rules")
    async def rules(_: str = Depends(require_service)):
        return {
            "pii": [{"id": r.id, "masks_as": f"[{r.label}]", "description": r.description} for r in PII_RULES],
            "secrets": [{"id": r.id, "description": r.description} for r in SECRET_RULES],
            "injection": [{"id": r.id, "weight": r.weight, "description": r.description} for r in INJECTION_RULES],
            "compliance": [{"id": r.id, "description": r.description} for r in PROMISSORY_RULES],
            "thresholds": {"block": settings.injection_block_score,
                           "llm_review": settings.injection_review_score},
        }

    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(body: AgentRequest, request: Request, _: str = Depends(require_service)):
        start = time.perf_counter()
        if body.skill not in SKILLS:
            return AgentResponse(agent="sentinel", status="error", error=f"unknown skill {body.skill}")
        try:
            payload = GuardInput.model_validate(body.input)
        except ValidationError as exc:
            return AgentResponse(agent="sentinel", status="error",
                                 error=f"invalid input: {exc.errors()[0]['msg']}")
        if len(payload.text) > settings.max_text_chars:
            return AgentResponse(agent="sentinel", status="error",
                                 error=f"text longer than {settings.max_text_chars} characters")

        engine: GuardEngine = request.app.state.engine
        if body.skill == "guard_input":
            result = await engine.guard_input(payload.text)
        else:
            result = await engine.guard_output(payload.text, payload.kind)

        ms = int((time.perf_counter() - start) * 1000)
        request.app.state.audit.record(
            trace_id=body.context.trace_id, user_id=body.context.user_id, skill=body.skill,
            kind=payload.kind, decision=result.decision, rules=[f.rule for f in result.findings],
            text=payload.text, injection_score=result.injection_score,
            llm_checked=result.llm_checked, duration_ms=ms)
        log.info("guard skill=%s decision=%s rules=%s ms=%s trace=%s", body.skill, result.decision,
                 [f.rule for f in result.findings], ms, body.context.trace_id)
        return AgentResponse(agent="sentinel", status="ok", output=result.model_dump())

    return app
