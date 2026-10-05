"""
Tests for the MCP server.

LEARN: mcp.Client can connect to an MCPServer object IN-PROCESS (no network),
so these tests exercise real MCP discovery and tool calls in milliseconds.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from mcp import Client

from config import Settings
from server import build_server

TOKEN = "test-service-token-abcdefghijklmnop"


@pytest.fixture
def server():
    return build_server(Settings(_env_file=None, service_token=TOKEN))


def call(server, tool, args=None):
    async def go():
        async with Client(server) as c:
            return await c.call_tool(tool, args or {})
    return asyncio.run(go())


def test_discovery_lists_five_read_only_tools(server):
    async def go():
        async with Client(server) as c:
            return (await c.list_tools()).tools
    tools = {t.name: t for t in asyncio.run(go())}
    assert set(tools) == {"list_clients", "get_client_profile", "get_holdings",
                          "get_recent_trades", "get_security_info"}
    assert all(t.annotations.read_only_hint for t in tools.values())
    assert tools["get_holdings"].input_schema["required"] == ["client_id"]


def test_list_clients(server):
    r = call(server, "list_clients")
    assert {c["client_id"] for c in r.structured_content["clients"]} == {"patel-001", "chen-002", "garcia-003"}


def test_profile_has_target_allocation(server):
    r = call(server, "get_client_profile", {"client_id": "patel-001"})
    assert r.structured_content["target_allocation_pct"] == {"equity": 60, "fixed_income": 35, "cash": 5}


def test_holdings_values(server):
    h = call(server, "get_holdings", {"client_id": "patel-001"}).structured_content
    assert h["total_market_value"] == 2_350_000
    aibf = next(p for p in h["positions"] if p["symbol"] == "AIBF")
    assert aibf["unrealized_gain_loss"] == -12_000 and aibf["account_type"] == "taxable"


def test_recent_trades_window(server):
    assert len(call(server, "get_recent_trades", {"client_id": "garcia-003", "days": 30})
               .structured_content["trades"]) == 1
    assert call(server, "get_recent_trades", {"client_id": "garcia-003", "days": 5}) \
        .structured_content["trades"] == []


def test_security_info_with_replacements(server):
    s = call(server, "get_security_info", {"symbol": "aibf"}).structured_content
    assert s["symbol"] == "AIBF" and s["replacements"] == ["GIBX"]


def test_unknown_client_is_a_clear_tool_error(server):
    r = call(server, "get_holdings", {"client_id": "nobody-999"})
    assert r.is_error and "No client with id 'nobody-999'" in r.content[0].text


def test_invalid_arguments_rejected_by_schema(server):
    assert call(server, "get_holdings", {"client_id": "x'; DROP TABLE"}).is_error
    assert call(server, "get_recent_trades", {"client_id": "patel-001", "days": 9999}).is_error
    assert call(server, "get_holdings", {}).is_error


def test_http_requires_token_but_health_is_public(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", TOKEN)
    from config import get_settings
    get_settings.cache_clear()
    from main import build_app
    with TestClient(build_app()) as c:
        assert c.get("/health").json()["status"] == "ok"
        assert c.post("/mcp", json={}).status_code == 401
        assert c.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    get_settings.cache_clear()


def test_refuses_weak_token(monkeypatch):
    monkeypatch.setenv("SERVICE_TOKEN", "replace-me")
    from config import get_settings
    get_settings.cache_clear()
    from main import build_app
    with pytest.raises(RuntimeError):
        build_app()
    get_settings.cache_clear()
