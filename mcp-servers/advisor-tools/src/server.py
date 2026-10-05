"""
The MCP server: the TOOLS any agent (or any MCP-capable AI app) can discover and call.

LEARN: What MCP gives you
  * DISCOVERY: a client asks "what tools do you have?" (tools/list) and gets
    each tool's name, description and JSON input schema, generated from the
    Python type hints below. Claude can read those schemas and decide which
    tool to call by itself.
  * A STANDARD CALL: tools/call with JSON arguments, returning structured JSON.
  * ONE SERVER, MANY CLIENTS: the Analyst uses these tools today. Tomorrow the
    Scribe, Claude Desktop or another team's agent can use the SAME server
    without new integration code. That's the "USB-C for AI" idea.

Design rules for these tools:
  * Read-only (annotated read_only_hint=True): nothing here can change data.
  * Small and specific: one job per tool, so a model can choose correctly.
  * Expected failures raise ToolError with a clear message the model can act on.
    Unexpected crashes are hidden by the SDK (the caller only sees a generic error).
"""

# NOTE: no "from __future__ import annotations" in this file. The MCP SDK reads the
# tools' type hints at runtime to build their JSON schemas, and deferred (string)
# hints that mention local variables can't be resolved.
import logging
import time
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import VERSION, Settings
from data_store import NotFound, PortfolioStore

log = logging.getLogger("advisor_tools")

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                            open_world_hint=False)

ClientId = Annotated[str, Field(description="Client household id, e.g. 'patel-001'",
                                pattern=r"^[A-Za-z0-9_-]{1,64}$")]


def build_server(settings: Settings) -> MCPServer:
    store = PortfolioStore(settings.data_dir)
    mcp = MCPServer(
        name="advisor-tools",
        version=VERSION,
        instructions="Read-only portfolio data for Aurelius advisors: client profiles, holdings, "
                     "recent trades and security reference data. Amounts are in USD.",
    )

    def run(tool: str, args: dict[str, Any], fn):
        """Audit + error translation around every tool."""
        start = time.perf_counter()
        try:
            result = fn()
            log.info("tool_call tool=%s args=%s ok ms=%d", tool, args, (time.perf_counter() - start) * 1000)
            return result
        except NotFound as exc:
            log.info("tool_call tool=%s args=%s not_found", tool, args)
            raise ToolError(str(exc)) from exc

    # ------------------------------------------------------------------ tools
    @mcp.tool(annotations=READ_ONLY)
    def list_clients() -> dict[str, Any]:
        """List the client households this advisor can see (id, household name, risk profile)."""
        return run("list_clients", {}, lambda: {"clients": store.list_clients()})

    @mcp.tool(annotations=READ_ONLY)
    def get_client_profile(client_id: ClientId) -> dict[str, Any]:
        """Get a household's risk profile, TARGET asset allocation (percent by asset class)
        and its accounts (taxable or IRA)."""
        return run("get_client_profile", {"client_id": client_id}, lambda: store.profile(client_id))

    @mcp.tool(annotations=READ_ONLY)
    def get_holdings(client_id: ClientId) -> dict[str, Any]:
        """Get every position in every account of a household: symbol, asset class,
        market value, cost basis, unrealized gain/loss, account type and purchase date."""
        return run("get_holdings", {"client_id": client_id}, lambda: store.holdings(client_id))

    @mcp.tool(annotations=READ_ONLY)
    def get_recent_trades(
        client_id: ClientId,
        days: Annotated[int, Field(ge=1, le=settings.max_trade_lookback_days,
                                   description="How many days back to look")] = 30,
    ) -> dict[str, Any]:
        """Get buys and sells across ALL of a household's accounts in the last N days
        (needed for wash-sale checks)."""
        return run("get_recent_trades", {"client_id": client_id, "days": days},
                   lambda: store.trades(client_id, days))

    @mcp.tool(annotations=READ_ONLY)
    def get_security_info(symbol: Annotated[str, Field(description="Ticker symbol, e.g. 'AIBF'")]) -> dict[str, Any]:
        """Get reference data for a security: name, type (stock/fund/cash), asset class,
        description, and 'replacements' (similar but NOT substantially identical funds)."""
        return run("get_security_info", {"symbol": symbol}, lambda: store.security(symbol))

    # ------------------------------------------------------- plain HTTP route
    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": "advisor-tools", "version": VERSION,
                             "data_as_of": store.as_of.isoformat(),
                             "clients": len(store.list_clients())})

    return mcp
