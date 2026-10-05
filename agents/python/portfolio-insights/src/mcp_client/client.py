"""
The Analyst's MCP CLIENT: the only place that talks to the advisor-tools server.

LEARN: The MCP flow, in three calls
  1. connect     open a session to http://127.0.0.1:8500/mcp (with our token)
  2. tools/list  "what can you do?" -> names, descriptions, JSON input schemas
  3. tools/call  get_holdings({"client_id": "patel-001"}) -> structured JSON

The Analyst never imports the server's code or reads its files. If the data
moves from JSON files to a real portfolio system, nothing here changes.
"""
from __future__ import annotations

import json
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

log = logging.getLogger("analyst.mcp")


class ToolCallError(Exception):
    """The MCP server reported an error (e.g. unknown client)."""


class MCPUnavailable(Exception):
    """Could not connect to the MCP server."""


class PortfolioTools:
    """
    Async context manager:
        async with PortfolioTools(url, token) as tools:
            holdings = await tools.call("get_holdings", client_id="patel-001")

    `target` may also be an in-process MCP server object (used by the tests).
    """

    def __init__(self, target: Any, token: str = "", timeout_s: float = 20.0):
        self.target, self.token, self.timeout_s = target, token, timeout_s
        self.calls: list[dict[str, Any]] = []  # every tool call, for transparency
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None

    async def __aenter__(self) -> "PortfolioTools":
        self._stack = AsyncExitStack()
        try:
            if isinstance(self.target, str):
                http = create_mcp_http_client(headers={"Authorization": f"Bearer {self.token}"})
                await self._stack.enter_async_context(http)
                transport = streamable_http_client(self.target, http_client=http)
                self._client = await self._stack.enter_async_context(
                    Client(transport, read_timeout_seconds=self.timeout_s))
            else:
                self._client = await self._stack.enter_async_context(Client(self.target))
        except BaseException as exc:  # connection refused, 401, timeout... arrive wrapped in groups
            await self._stack.aclose()
            log.warning("mcp_connect_failed target=%s error=%s", self.target, _root(exc))
            raise MCPUnavailable(f"Cannot reach the portfolio data service (MCP): {_root(exc)}") from None
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack:
            await self._stack.aclose()

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._client.list_tools()
        return [{"name": t.name, "description": t.description or "",
                 "input_schema": t.input_schema,
                 "read_only": bool(t.annotations and t.annotations.read_only_hint)}
                for t in result.tools]

    async def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        result = await self._client.call_tool(tool, arguments)
        self.calls.append({"tool": tool, "arguments": arguments, "is_error": result.is_error})
        if result.is_error:
            text = result.content[0].text if result.content else "tool error"
            raise ToolCallError(text)
        if result.structured_content is not None:
            return dict(result.structured_content)
        return json.loads(result.content[0].text)  # servers without structured output


def _root(exc: BaseException) -> str:
    """Dig the real cause out of anyio ExceptionGroups for a readable message."""
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {str(exc)[:150]}"
