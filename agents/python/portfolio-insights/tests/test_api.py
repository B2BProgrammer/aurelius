"""End-to-end tests: HTTP API -> MCP client -> fake MCP server (in-process)."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import Settings
from llm.tool_agent import ToolAgent
from mcp_client.client import MCPUnavailable, PortfolioTools

from conftest import SERVICE_TOKEN, build_fake_mcp, invoke


def test_health_reports_mcp_up(client):
    h = client.get("/health").json()
    assert h["agent"] == "analyst" and h["mcp_server"]["status"] == "up" and h["mcp_server"]["tools"] == 5


def test_agent_card_has_both_skills(client):
    assert set(client.get("/.well-known/agent.json").json()["skills"]) == {"analyze_portfolio", "ask_portfolio"}


def test_auth_required(client):
    assert client.post("/invoke", json={"skill": "x", "input": {},
                                        "context": {"trace_id": "t", "user_id": "u"}}).status_code == 401
    assert client.get("/v1/tools").status_code == 401


def test_tools_discovered_over_mcp(client, auth):
    names = [t["name"] for t in client.get("/v1/tools", headers=auth).json()["tools"]]
    assert "get_holdings" in names and "get_recent_trades" in names


def test_analyze_busy_household(client, auth):
    r = invoke(client, auth, "analyze_portfolio", client_id="busy-01")
    o = r["output"]
    assert r["status"] == "ok" and o["allocation"]["needs_rebalance"]
    assert o["concentration"][0]["symbol"] == "BIGCO"
    assert [i["symbol"] for i in o["tax_loss_ideas"]] == ["BOND"]
    assert o["mcp_tools_used"][:3] == ["get_client_profile", "get_holdings", "get_recent_trades"]
    assert o["answered_by"] == "template" and "Busy household" in o["summary"]


def test_analyze_calm_household(client, auth):
    o = invoke(client, auth, "analyze_portfolio", client_id="calm-02")["output"]
    assert o["actions"][0].startswith("No action needed")


def test_client_id_from_context(client, auth):
    body = {"skill": "analyze_portfolio", "input": {},
            "context": {"trace_id": "t", "user_id": "u", "client_id": "calm-02"}}
    assert client.post("/invoke", headers=auth, json=body).json()["status"] == "ok"


@pytest.mark.parametrize("skill,inp,err", [
    ("analyze_portfolio", {"client_id": "nobody-9"}, "No client with id"),
    ("analyze_portfolio", {"client_id": "bad id!"}, "invalid input"),
    ("analyze_portfolio", {}, "invalid input"),
    ("ask_portfolio", {"client_id": "busy-01", "question": "What do they own?"}, "needs ANTHROPIC_API_KEY"),
    ("rebalance_now", {"client_id": "busy-01"}, "unknown skill"),
])
def test_errors_in_envelope(client, auth, skill, inp, err):
    r = invoke(client, auth, skill, **inp)
    assert r["status"] == "error" and err in r["error"]


def test_mcp_down_is_reported_not_crashed(settings, auth):
    with TestClient(create_app(settings, mcp_target="http://127.0.0.1:1/mcp")) as c:
        assert c.get("/health").json()["mcp_server"]["status"] == "down"
        r = invoke(c, auth, "analyze_portfolio", client_id="busy-01")
        assert r["status"] == "error" and "Cannot reach" in r["error"]


# ------------------------------------------------- the Claude <-> MCP tool loop
class FakeClaude:
    """Scripted 'Claude': first asks for get_holdings for ANOTHER client, then answers."""

    def __init__(self):
        self.calls = 0
        self.seen_tools = []
        self.messages = SimpleNamespace(create=self.create)

    async def create(self, **kw):
        self.calls += 1
        self.seen_tools = [t["name"] for t in kw["tools"]]
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        if self.calls == 1:
            block = SimpleNamespace(type="tool_use", id="tu1", name="get_holdings",
                                    input={"client_id": "calm-02"})  # tries to read someone else
            return SimpleNamespace(stop_reason="tool_use", content=[block], usage=usage)
        last = kw["messages"][-1]["content"][0]["content"]
        text = "They hold BigCo." if "BIGCO" in last else "wrong client!"
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)],
                               usage=usage)


def test_tool_loop_with_scope_pinning(settings):
    fake = FakeClaude()
    agent = ToolAgent(settings, client=fake)

    async def go():
        async with PortfolioTools(build_fake_mcp()) as tools:
            return await agent.ask(tools, "busy-01", "What stock do they hold?")

    res = asyncio.run(go())
    assert "list_clients" not in fake.seen_tools                  # allowlist
    assert res.tool_calls[0]["arguments"]["client_id"] == "busy-01"  # pinned, not calm-02
    assert res.answer == "They hold BigCo." and res.turns == 2


def test_refuses_weak_token():
    with pytest.raises(RuntimeError):
        create_app(Settings(_env_file=None, service_token="replace-me"))


def test_bad_token_to_real_url_is_mcp_unavailable():
    async def go():
        async with PortfolioTools("http://127.0.0.1:1/mcp", SERVICE_TOKEN):
            pass
    with pytest.raises(MCPUnavailable):
        asyncio.run(go())
