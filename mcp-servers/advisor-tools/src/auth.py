"""
Bearer-token check in front of the MCP endpoint.

LEARN: An MCP server that exposes client data must authenticate callers like
any other API. This is plain ASGI middleware: it runs before the MCP SDK sees
the request. /health stays public so monitoring can reach it.

(The MCP spec also defines a full OAuth 2.1 flow for MCP servers, which the
SDK supports via auth=/token_verifier=. A shared service token is the simple
equivalent for agent-to-agent calls inside one system.)
"""
from __future__ import annotations

import hmac
import json

PUBLIC_PATHS = {"/health"}
_WEAK = {"", "replace-me", "replace-with-long-random-string"}


class BearerTokenMiddleware:
    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in PUBLIC_PATHS:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode()
        supplied = auth[7:] if auth.lower().startswith("bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied, self.token):
            body = json.dumps({"error": "unauthorized", "detail": "Invalid or missing bearer token"}).encode()
            await send({"type": "http.response.start", "status": 401,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"www-authenticate", b"Bearer")]})
            await send({"type": "http.response.body", "body": body})
            return
        return await self.app(scope, receive, send)


def check_token(token: str) -> None:
    if token in _WEAK or len(token) < 24:
        raise RuntimeError("SERVICE_TOKEN is missing or too short (24+ chars) in aurelius\\.env")
