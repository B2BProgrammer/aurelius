"""
Executor: runs a Plan by calling agents.

LEARN:
  * asyncio.gather runs every step of a stage AT THE SAME TIME, so a stage
    takes as long as its slowest agent, not the sum of all of them.
  * Each step is isolated: if one agent fails, the others still return
    (the answer just says that part was unavailable).
  * Every call carries a service token (agent-to-agent auth) and a trace id.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

import httpx

from agents import mock_agents
from core.config import Settings
from schemas.models import AgentRequest, AgentResponse, InvokeContext, Plan, PlanStep, StepResult
from agents.registry import AgentInfo

log = logging.getLogger("conductor.executor")

Responder = Callable[[str, AgentRequest], Awaitable[AgentResponse]]


class AgentClient:
    """Calls one agent's POST /invoke. Real HTTP, or the mock when MOCK_AGENTS=true."""

    def __init__(self, settings: Settings, registry: dict[str, AgentInfo],
                 http: httpx.AsyncClient, mock_responder: Responder | None = None):
        self.settings, self.registry, self.http = settings, registry, http
        self.mock_responder = mock_responder or (mock_agents.respond if settings.mock_agents else None)

    async def call(self, agent: str, skill: str, payload: dict, ctx: InvokeContext) -> AgentResponse:
        req = AgentRequest(skill=skill, input=payload, context=ctx)
        if self.mock_responder is not None and agent not in self.settings.real_agent_set:
            return await self.mock_responder(agent, req)

        info = self.registry[agent]
        headers = {"Authorization": f"Bearer {self.settings.service_token}",
                   "X-Trace-Id": ctx.trace_id}
        last_error = "unknown error"
        for attempt in range(2):  # 1 retry for transient failures
            try:
                r = await self.http.post(f"{info.url}/invoke", json=req.model_dump(),
                                         headers=headers, timeout=self.settings.agent_timeout_s)
                if r.status_code >= 500:
                    last_error = f"HTTP {r.status_code}"
                elif r.status_code >= 400:
                    # 4xx = our request was wrong; retrying won't help
                    return AgentResponse(agent=agent, status="error", error=f"HTTP {r.status_code}")
                else:
                    return AgentResponse.model_validate(r.json())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = type(exc).__name__
            except ValueError:  # bad JSON / doesn't match the contract
                return AgentResponse(agent=agent, status="error", error="invalid response format")
            if attempt == 0:
                await asyncio.sleep(0.3)
        return AgentResponse(agent=agent, status="error", error=f"unavailable ({last_error})")


async def _run_step(client: AgentClient, step: PlanStep, ctx: InvokeContext,
                    prior: dict[str, dict]) -> StepResult:
    start = time.perf_counter()
    payload = dict(step.input)
    if prior:
        payload["prior_results"] = prior  # later stages can use earlier outputs
    try:
        resp = await client.call(step.agent, step.skill, payload, ctx)
    except Exception as exc:  # never let one agent crash the whole request
        log.exception("step_crashed agent=%s", step.agent)
        resp = AgentResponse(agent=step.agent, status="error", error=type(exc).__name__)
    ms = int((time.perf_counter() - start) * 1000)
    log.info("step agent=%s skill=%s status=%s ms=%s trace=%s",
             step.agent, step.skill, resp.status, ms, ctx.trace_id)
    return StepResult(agent=step.agent, skill=step.skill, status=resp.status,
                      duration_ms=ms, output=resp.output, error=resp.error)


async def run_plan(plan: Plan, client: AgentClient, ctx: InvokeContext) -> list[StepResult]:
    results: list[StepResult] = []
    prior: dict[str, dict] = {}
    for stage in plan.stages:
        stage_results = await asyncio.gather(*(_run_step(client, s, ctx, prior) for s in stage))
        for r in stage_results:
            results.append(r)
            if r.status == "ok":
                prior[f"{r.agent}.{r.skill}"] = r.output
    return results
