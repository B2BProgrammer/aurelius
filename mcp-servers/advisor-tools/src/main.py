"""
ENTRY POINT of the advisor-tools MCP server.

Run from the advisor-tools folder (venv active):
    python src\\main.py

    MCP endpoint : http://127.0.0.1:8500/mcp     (needs Bearer SERVICE_TOKEN)
    Health       : http://127.0.0.1:8500/health  (public)
"""
import logging
import sys

import uvicorn

from auth import BearerTokenMiddleware, check_token
from config import get_settings
from server import build_server


def build_app():
    settings = get_settings()
    check_token(settings.service_token)  # fail closed
    app = build_server(settings).streamable_http_app(host=settings.host)
    return BearerTokenMiddleware(app, settings.service_token)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
    s = get_settings()
    print(f"advisor-tools MCP server on http://{s.host}:{s.port}/mcp  (health: /health)")
    uvicorn.run(build_app(), host=s.host, port=s.port, log_level="warning")
