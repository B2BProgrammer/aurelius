"""
Analyst HTTP API.

Endpoints
  GET  /health                  liveness + whether the MCP server is reachable (no auth)
  GET  /.well-known/agent.json  agent card with input/output schemas (no auth)
  POST /invoke                  agent contract: analyze_portfolio | ask_portfolio (service token)
  GET  /v1/tools                the MCP tools this agent discovered (service token)

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

from analysis.engine import analyze
from core.config import VERSION, Settings, get_settings
from llm.narrator import Narrator
from llm.tool_agent import LLMUnavailable, ToolAgent
from mcp_client.client import MCPUnavailable, PortfolioTools, ToolCallError
from schemas.models import (AgentRequest, AgentResponse, AnalysisResult, AnalyzeInput, AskInput,
                            AskResult)
from security.auth import check_startup_security, require_service

log = logging.getLogger("analyst.api")

SKILLS = {
    "analyze_portfolio": ("Allocation drift, single-stock concentration and tax-loss ideas for one household, "
                          "computed from live portfolio data (via MCP).", AnalyzeInput, AnalysisResult),
    "ask_portfolio": ("Free-form question about one household; Claude picks which MCP tools to call. "
                      "Needs an API key.", AskInput, AskResult),
}


def create_app(settings: Settings | None = None, mcp_target: Any = None, llm_client: Any = None) -> FastAPI:
    """mcp_target: MCP URL (default from settings) or an in-process MCP server (tests)."""
    settings = settings or get_settings()
    check_startup_security(settings)
    target = mcp_target or settings.mcp_advisor_tools_url

    app = FastAPI(title="Aurelius Analyst (portfolio-insights)", version=VERSION)
    app.state.settings = settings
    app.state.narrator = Narrator(settings)
    app.state.agent = ToolAgent(settings, client=llm_client)

    def tools() -> PortfolioTools:
        return PortfolioTools(target, settings.service_token, settings.mcp_timeout_s)

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
        try:
            async with tools() as t:
                n = len(await t.list_tools())
            mcp = {"status": "up", "tools": n}
        except MCPUnavailable as exc:
            mcp = {"status": "down", "error": str(exc)}
        return {"status": "ok", "agent": "analyst", "version": VERSION,
                "mcp_server": {"url": target if isinstance(target, str) else "in-process", **mcp},
                "llm": settings.use_llm}

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": "analyst", "codename": "Analyst", "folder": "portfolio-insights",
            "language": "Python", "version": VERSION,
            "description": "Portfolio analytics for a client household, using portfolio data from MCP tools.",
            "auth": "Bearer SERVICE_TOKEN",
            "depends_on": {"mcp_server": "advisor-tools"},
            "endpoints": {"invoke": "/invoke", "tools": "/v1/tools"},
            "skills": {name: {"description": d, "input_schema": i.model_json_schema(),
                              "output_schema": o.model_json_schema()}
                       for name, (d, i, o) in SKILLS.items()},
        }

    @app.get("/v1/tools")
    async def list_mcp_tools(_: str = Depends(require_service)):
        try:
            async with tools() as t:
                return {"mcp_server": target if isinstance(target, str) else "in-process",
                        "tools": await t.list_tools()}
        except MCPUnavailable as exc:
            return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(body: AgentRequest, request: Request, _: str = Depends(require_service)):
        start = time.perf_counter()
        if body.skill not in SKILLS:
            return AgentResponse(agent="analyst", status="error", error=f"unknown skill {body.skill}")
        model = SKILLS[body.skill][1]
        data = {k: v for k, v in body.input.items() if k in model.model_fields}
        data.setdefault("client_id", body.context.client_id)   # Conductor may send it in context
        try:
            params = model.model_validate(data)
        except ValidationError as exc:
            err = exc.errors()[0]
            return AgentResponse(agent="analyst", status="error",
                                 error=f"invalid input: {err['loc'][0] if err['loc'] else ''} {err['msg']}")
        try:
            async with tools() as t:
                if body.skill == "analyze_portfolio":
                    result = await analyze(t, params.client_id, settings, request.app.state.narrator)
                else:
                    result = await request.app.state.agent.ask(t, params.client_id, params.question)
                used = [c["tool"] for c in t.calls]
        except (MCPUnavailable, LLMUnavailable) as exc:
            return AgentResponse(agent="analyst", status="error", error=str(exc))
        except ToolCallError as exc:
            return AgentResponse(agent="analyst", status="error", error=f"portfolio data: {exc}")

        log.info("invoke skill=%s client=%s mcp_calls=%s ms=%d trace=%s", body.skill, params.client_id,
                 used, (time.perf_counter() - start) * 1000, body.context.trace_id)
        return AgentResponse(agent="analyst", status="ok", output=result.model_dump())

    return app
