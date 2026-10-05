"""
A tiny MCP CLIENT: connect, discover the tools, call one.
This is exactly what the Analyst does inside, minus the analysis.

Usage (advisor-tools folder, venv active, server running in another terminal):
    python scripts\\try_mcp.py                       # list tools + get_holdings for patel-001
    python scripts\\try_mcp.py get_recent_trades garcia-003
    python scripts\\try_mcp.py get_security_info AIBF
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcp import Client  # noqa: E402
from mcp.client.streamable_http import streamable_http_client  # noqa: E402
from mcp.shared._httpx_utils import create_mcp_http_client  # noqa: E402

from config import get_settings  # noqa: E402


async def main(tool: str, arg: str) -> None:
    s = get_settings()
    url = f"http://{s.host}:{s.port}/mcp"
    http = create_mcp_http_client(headers={"Authorization": f"Bearer {s.service_token}"})
    async with http, Client(streamable_http_client(url, http_client=http)) as client:
        print(f"Connected to {url}\n\n=== tools/list (DISCOVERY) ===")
        for t in (await client.list_tools()).tools:
            params = ", ".join(t.input_schema.get("properties", {}))
            print(f"- {t.name}({params})\n    {t.description.splitlines()[0]}")

        key = "symbol" if tool == "get_security_info" else "client_id"
        args = {} if tool == "list_clients" else {key: arg}
        print(f"\n=== tools/call {tool} {args} ===")
        result = await client.call_tool(tool, args)
        if result.is_error:
            print("TOOL ERROR:", result.content[0].text)
        else:
            print(json.dumps(result.structured_content, indent=2))


if __name__ == "__main__":
    tool = sys.argv[1] if len(sys.argv) > 1 else "get_holdings"
    arg = sys.argv[2] if len(sys.argv) > 2 else "patel-001"
    asyncio.run(main(tool, arg))
