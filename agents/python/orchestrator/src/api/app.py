"""
The FastAPI app: HTTP endpoints, CORS, security headers, error handling.

Endpoints
  GET  /health                  liveness check (no auth)
  GET  /.well-known/agent.json  agent card: who I am, what I can do (no auth)
  GET  /v1/agents               the swarm and each agent's status (advisor JWT)
  POST /v1/chat                 main endpoint for the apps: ask anything (advisor JWT)
  POST /invoke                  standard agent contract (service token)
  /v1/auth, /v1/clients, /v1/skills, /v1/drafts, /v1/stream   screen-shaped endpoints
                                for the web and mobile apps: see api/apps.py

Started by src/main.py.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.apps import router as apps_router
from core.config import VERSION as __version__
from core.config import Settings, get_settings
from orchestration.executor import AgentClient
from security.guardrails import GuardrailBlocked, GuardrailUnavailable, Guardrails
from llm.client import LLMClient
from schemas.models import AgentRequest, AgentResponse, ChatRequest, ChatResponse
from orchestration.pipeline import Pipeline
from orchestration.planner import Planner
from agents.registry import build_registry
from security.auth import check_startup_security, require_service, require_user
from orchestration.synthesizer import Synthesizer

log = logging.getLogger("conductor.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    check_startup_security(settings)  # refuse to start if insecure

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # LEARN: one shared HTTP client = connection pooling (much faster than one per call)
        async with httpx.AsyncClient() as http:
            registry = build_registry(settings)
            llm = LLMClient(settings)
            client = AgentClient(settings, registry, http)
            app.state.registry = registry
            app.state.agent_client = client
            app.state.pipeline = Pipeline(
                planner=Planner(llm, registry, settings),
                client=client,
                guardrails=Guardrails(client, settings),
                synthesizer=Synthesizer(llm),
            )
            app.state.http = http
            log.info("conductor_started model=%s mock_llm=%s mock_agents=%s auth_required=%s",
                     settings.llm_model, llm.mock, settings.mock_agents, settings.auth_required)
            yield

    app = FastAPI(title="Aurelius Conductor", version=__version__, lifespan=lifespan)
    app.state.settings = settings

    # LEARN: CORS = which websites may call this API from a browser. Only Atrium.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
        expose_headers=["X-Trace-Id"],   # the apps show the trace id so a request can be found in the logs
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        request.state.trace_id = request.headers.get("X-Trace-Id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"  # don't cache client data
        return response

    # LEARN: never return stack traces to callers; give them a trace id instead
    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        trace = getattr(request.state, "trace_id", "unknown")
        log.exception("unhandled_error trace=%s", trace)
        return JSONResponse(status_code=500,
                            content={"detail": "Internal error", "trace_id": trace})

    # ------------------------------------------------------------------ routes
    @app.get("/health")
    async def health():
        return {"status": "ok", "agent": settings.agent_name, "version": __version__}

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": "conductor",
            "codename": "Conductor",
            "language": "Python",
            "version": __version__,
            "description": "Supervisor of the Aurelius swarm: plans, routes, merges answers.",
            "skills": {"chat": "Answer an advisor request using the other agents. "
                               "input: {message, client_id?}"},
            "endpoints": {"invoke": "/invoke", "chat": "/v1/chat"},
        }

    @app.get("/v1/agents")
    async def list_agents(request: Request, user: str = Depends(require_user)):
        registry = request.app.state.registry

        async def status_of(info):
            if settings.is_mocked(info.name):
                return "mock"
            try:
                r = await request.app.state.http.get(f"{info.url}/health", timeout=2.0)
                return "up" if r.status_code == 200 else "down"
            except httpx.HTTPError:
                return "down"

        statuses = await asyncio.gather(*(status_of(a) for a in registry.values()))
        return [
            {"name": a.name, "codename": a.codename, "language": a.language,
             "url": a.url, "skills": list(a.skills), "status": s}
            for a, s in zip(registry.values(), statuses)
        ]

    async def _run(req: ChatRequest, user: str, request: Request) -> ChatResponse:
        if len(req.message) > settings.max_message_chars:
            raise HTTPException(413, detail=f"Message longer than {settings.max_message_chars} characters")
        try:
            return await request.app.state.pipeline.handle(req, user, request.state.trace_id)
        except GuardrailBlocked as exc:
            raise HTTPException(400, detail=f"Request blocked by security policy: {exc}")
        except GuardrailUnavailable:
            raise HTTPException(503, detail="Security service unavailable; request refused")

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request, user: str = Depends(require_user)):
        return await _run(body, user, request)

    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(body: AgentRequest, request: Request, _: str = Depends(require_service)):
        if body.skill != "chat":
            return AgentResponse(agent="conductor", status="error", error=f"unknown skill {body.skill}")
        chat_req = ChatRequest(message=str(body.input.get("message", "")),
                               client_id=body.input.get("client_id") or body.context.client_id)
        result = await _run(chat_req, body.context.user_id, request)
        return AgentResponse(agent="conductor", status="ok", output=result.model_dump())

    app.include_router(apps_router)
    return app
