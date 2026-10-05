"""
Shared test setup.

LEARN: The tests start a small FAKE MCP server in-process, with the same tool
names and result shapes as the real advisor-tools server. The Analyst can't
tell the difference, which proves it depends only on the MCP contract, not
on how or where the data is stored.
"""
# (no "from __future__ import annotations": MCP reads the tool type hints at runtime)
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from api.app import create_app
from core.config import Settings

SERVICE_TOKEN = "test-service-token-abcdefghijklmnop"

SECURITIES = {
    "BIGCO": {"name": "BigCo Inc", "security_type": "stock", "asset_class": "equity"},
    "TOTAL": {"name": "Total Market Fund", "security_type": "fund", "asset_class": "equity", "replacements": ["TOTL2"]},
    "BOND": {"name": "Bond Fund", "security_type": "fund", "asset_class": "fixed_income", "replacements": ["BOND2"]},
    "CASH": {"name": "Money Market", "security_type": "cash", "asset_class": "cash"},
}


def pos(account_id, account_type, symbol, value, cost):
    s = SECURITIES[symbol]
    return {"account_id": account_id, "account_type": account_type, "symbol": symbol, "name": s["name"],
            "security_type": s["security_type"], "asset_class": s["asset_class"], "quantity": 1,
            "price": value, "market_value": value, "cost_basis": cost,
            "unrealized_gain_loss": value - cost, "acquired": "2020-01-01"}


CLIENTS = {
    # 70/20/10 vs 60/35/5 target, BigCo 20 %, a $5,000 taxable bond loss, a $9,000 IRA loss (ignored)
    "busy-01": {
        "profile": {"household": "Busy household", "risk_profile": "moderate",
                    "target_allocation_pct": {"equity": 60, "fixed_income": 35, "cash": 5}},
        "positions": [pos("B-TAX", "taxable", "BIGCO", 200_000, 50_000),
                      pos("B-TAX", "taxable", "TOTAL", 500_000, 400_000),
                      pos("B-TAX", "taxable", "BOND", 95_000, 100_000),
                      pos("B-IRA", "ira", "BOND", 105_000, 114_000),
                      pos("B-TAX", "taxable", "CASH", 100_000, 100_000)],
        "trades": [],
    },
    # exactly on target, nothing to do
    "calm-02": {
        "profile": {"household": "Calm family", "risk_profile": "conservative",
                    "target_allocation_pct": {"equity": 40, "fixed_income": 55, "cash": 5}},
        "positions": [pos("C-TAX", "taxable", "TOTAL", 400_000, 300_000),
                      pos("C-TAX", "taxable", "BOND", 550_000, 500_000),
                      pos("C-TAX", "taxable", "CASH", 50_000, 50_000)],
        "trades": [],
    },
}


def build_fake_mcp(clients=CLIENTS) -> MCPServer:
    mcp = MCPServer(name="fake-advisor-tools")

    def get(cid: str) -> dict:
        if cid not in clients:
            raise ToolError(f"No client with id '{cid}'")
        return clients[cid]

    @mcp.tool()
    def list_clients() -> dict[str, Any]:
        """List clients."""
        return {"clients": [{"client_id": c} for c in clients]}

    @mcp.tool()
    def get_client_profile(client_id: str) -> dict[str, Any]:
        """Profile and target allocation."""
        return {"client_id": client_id, **get(client_id)["profile"], "accounts": []}

    @mcp.tool()
    def get_holdings(client_id: str) -> dict[str, Any]:
        """Positions."""
        p = get(client_id)["positions"]
        return {"client_id": client_id, "as_of": "2026-10-01",
                "total_market_value": sum(x["market_value"] for x in p), "positions": p}

    @mcp.tool()
    def get_recent_trades(client_id: str, days: int = 30) -> dict[str, Any]:
        """Recent trades."""
        return {"client_id": client_id, "trades": get(client_id)["trades"]}

    @mcp.tool()
    def get_security_info(symbol: str) -> dict[str, Any]:
        """Security reference data."""
        if symbol not in SECURITIES:
            raise ToolError(f"Unknown security '{symbol}'")
        return {"symbol": symbol, **SECURITIES[symbol]}

    return mcp


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, service_token=SERVICE_TOKEN, llm_mock=True)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, mcp_target=build_fake_mcp())) as c:
        yield c


@pytest.fixture
def auth() -> dict:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def invoke(client, auth, skill, **inp) -> dict:
    body = {"skill": skill, "input": inp, "context": {"trace_id": "test", "user_id": "advisor-007"}}
    return client.post("/invoke", headers=auth, json=body).json()
