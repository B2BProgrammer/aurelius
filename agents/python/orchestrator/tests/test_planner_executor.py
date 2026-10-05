"""Unit tests for planning and parallel execution."""
import asyncio
import time

import httpx

from agents import mock_agents
from orchestration.executor import AgentClient, run_plan
from schemas.models import AgentResponse, InvokeContext, Plan, PlanStep
from orchestration.planner import rule_based_plan, validate_plan
from agents.registry import build_registry

CTX = InvokeContext(trace_id="t", user_id="u", client_id="patel-001")  # mocks now answer like the real agents: unknown clients fail


def test_validate_plan_drops_bad_steps(settings):
    registry = build_registry(settings)
    raw = {"stages": [[
        {"agent": "analyst", "skill": "analyze_portfolio", "reason": "ok"},
        {"agent": "hacker", "skill": "steal", "reason": "unknown agent"},
        {"agent": "analyst", "skill": "delete_all", "reason": "unknown skill"},
        {"agent": "sentinel", "skill": "guard_input", "reason": "not plannable"},
    ]]}
    plan = validate_plan(raw, registry, settings, "c1", "llm")
    assert [(s.agent, s.skill) for s in plan.stages[0]] == [("analyst", "analyze_portfolio")]
    assert plan.stages[0][0].input["client_id"] == "c1"


def test_validate_plan_caps_size(settings):
    registry = build_registry(settings)
    step = {"agent": "pulse", "skill": "get_events", "reason": "x"}
    raw = {"stages": [[step]] * 10}
    assert len(validate_plan(raw, registry, settings, None, "llm").stages) == settings.max_plan_stages


def test_rule_planner_orders_email_last(settings):
    plan = rule_based_plan("Prep me for the review and draft an email",
                           build_registry(settings), settings, "c1")
    assert plan.source == "rules"
    assert plan.stages[-1][0].agent == "herald"


def test_stage_runs_in_parallel(settings):
    """5 agents x 0.2s each should take ~0.2s, not ~1s."""
    async def slow(agent, req):
        await asyncio.sleep(0.2)
        return AgentResponse(agent=agent, status="ok", output={"agent": agent})

    async def go():
        async with httpx.AsyncClient() as http:
            client = AgentClient(settings, build_registry(settings), http, mock_responder=slow)
            plan = Plan(stages=[[PlanStep(agent=a, skill="x") for a in
                                 ["liaison", "scribe", "analyst", "notary", "pulse"]]])
            start = time.perf_counter()
            await run_plan(plan, client, CTX)
            return time.perf_counter() - start

    assert asyncio.run(go()) < 0.6


def test_one_failing_agent_does_not_break_others(settings):
    async def flaky(agent, req):
        if agent == "notary":
            raise ConnectionError("notary is down")
        return await mock_agents.respond(agent, req)

    async def go():
        async with httpx.AsyncClient() as http:
            client = AgentClient(settings, build_registry(settings), http, mock_responder=flaky)
            plan = Plan(stages=[[PlanStep(agent="notary", skill="check_kyc"),
                                 PlanStep(agent="analyst", skill="analyze_portfolio")]])
            return await run_plan(plan, client, CTX)

    results = {r.agent: r for r in asyncio.run(go())}
    assert results["notary"].status == "error"
    assert results["analyst"].status == "ok"


def test_later_stage_receives_prior_results(settings):
    seen = {}

    async def spy(agent, req):
        seen[agent] = req.input
        return await mock_agents.respond(agent, req)

    async def go():
        async with httpx.AsyncClient() as http:
            client = AgentClient(settings, build_registry(settings), http, mock_responder=spy)
            plan = Plan(stages=[[PlanStep(agent="pulse", skill="get_events")],
                                [PlanStep(agent="librarian", skill="search_knowledge")]])
            await run_plan(plan, client, CTX)

    asyncio.run(go())
    assert "pulse.get_events" in seen["librarian"]["prior_results"]
