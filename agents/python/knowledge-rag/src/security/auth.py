"""
Only other agents (holding the shared SERVICE_TOKEN) may call the Librarian.
Same pattern as Sentinel: constant-time compare, refuse to start with a weak token.
"""
from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import Settings

_bearer = HTTPBearer(auto_error=False)
_WEAK = {"", "replace-me", "replace-with-long-random-string"}


def require_service(request: Request,
                    creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    settings: Settings = request.app.state.settings
    if creds is None or not hmac.compare_digest(creds.credentials, settings.service_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing service token",
                            headers={"WWW-Authenticate": "Bearer"})
    return "service"


def check_startup_security(settings: Settings) -> None:
    if settings.service_token in _WEAK or len(settings.service_token) < 24:
        raise RuntimeError(
            "SERVICE_TOKEN is missing or too short (need 24+ chars) in aurelius\\.env. "
            "Use the same value the Conductor uses.")
