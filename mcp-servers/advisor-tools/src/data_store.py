"""
The data behind the tools: a read-only "portfolio system".

LEARN: In a real firm this module would call the custodian / portfolio
accounting system (often several). The point of an MCP server is that the
agents never know or care: they call get_holdings and get the same shape
whether the data comes from JSON files, a database or five back-end APIs.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SYMBOL = re.compile(r"^[A-Z0-9.]{1,10}$")


class NotFound(Exception):
    """A client or security that doesn't exist (an expected, explainable failure)."""


class PortfolioStore:
    def __init__(self, data_dir: Path):
        self._portfolios = json.loads((data_dir / "portfolios.json").read_text(encoding="utf-8"))
        self._securities = json.loads((data_dir / "securities.json").read_text(encoding="utf-8"))
        self.as_of = date.fromisoformat(self._portfolios["as_of"])

    # ------------------------------------------------------------ helpers
    def _client(self, client_id: str) -> dict[str, Any]:
        if not CLIENT_ID.match(client_id or ""):
            raise NotFound("client_id must be 1-64 letters, digits, '-' or '_'")
        client = self._portfolios["clients"].get(client_id)
        if client is None:
            raise NotFound(f"No client with id '{client_id}'")
        return client

    def security(self, symbol: str) -> dict[str, Any]:
        symbol = (symbol or "").upper()
        if not SYMBOL.match(symbol) or symbol not in self._securities:
            raise NotFound(f"Unknown security '{symbol}'")
        return {"symbol": symbol, **self._securities[symbol]}

    # ------------------------------------------------------------ queries
    def list_clients(self) -> list[dict[str, str]]:
        return [{"client_id": cid, "household": c["household"], "risk_profile": c["risk_profile"]}
                for cid, c in self._portfolios["clients"].items()]

    def profile(self, client_id: str) -> dict[str, Any]:
        c = self._client(client_id)
        return {"client_id": client_id, "household": c["household"], "risk_profile": c["risk_profile"],
                "target_allocation_pct": c["target_allocation"], "accounts": c["accounts"]}

    def holdings(self, client_id: str) -> dict[str, Any]:
        c = self._client(client_id)
        account_type = {a["account_id"]: a["type"] for a in c["accounts"]}
        positions = []
        for p in c["positions"]:
            sec = self._securities[p["symbol"]]
            value = round(p["quantity"] * p["price"], 2)
            positions.append({
                "account_id": p["account_id"], "account_type": account_type[p["account_id"]],
                "symbol": p["symbol"], "name": sec["name"], "security_type": sec["security_type"],
                "asset_class": sec["asset_class"], "quantity": p["quantity"], "price": p["price"],
                "market_value": value, "cost_basis": p["cost_basis"],
                "unrealized_gain_loss": round(value - p["cost_basis"], 2), "acquired": p["acquired"],
            })
        return {"client_id": client_id, "as_of": self.as_of.isoformat(),
                "total_market_value": round(sum(p["market_value"] for p in positions), 2),
                "positions": positions}

    def trades(self, client_id: str, days: int) -> dict[str, Any]:
        c = self._client(client_id)
        since = self.as_of - timedelta(days=days)
        recent = [t for t in c["trades"] if date.fromisoformat(t["date"]) >= since]
        return {"client_id": client_id, "as_of": self.as_of.isoformat(), "since": since.isoformat(),
                "trades": recent}
