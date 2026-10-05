"""
Authentication.

LEARN: Two kinds of callers, two kinds of credentials.
  * Humans (via Atrium) send a JWT: a signed token saying who they are and
    when it expires. We verify the signature, expiry, issuer and audience.
  * Other agents send a shared SERVICE_TOKEN. compare_digest compares it in
    constant time, so attackers can't guess it byte-by-byte from timing.
In production you'd use your identity provider's tokens (Okta, Entra ID)
and mTLS between services, but the ideas are the same.
"""
from __future__ import annotations

import hmac
import time

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import Settings

_bearer = HTTPBearer(auto_error=False)


def create_token(settings: Settings, subject: str, minutes: int = 60, role: str = "advisor") -> str:
    """Creates a dev token. In production the identity provider does this."""
    now = int(time.time())
    claims = {"sub": subject, "role": role, "iat": now, "exp": now + minutes * 60,
              "iss": settings.jwt_issuer, "aud": settings.jwt_audience}
    return jwt.encode(claims, settings.jwt_signing_key, algorithm="HS256")


def _unauthorized(detail: str = "Invalid or missing credentials") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def require_user(request: Request,
                 creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    settings: Settings = request.app.state.settings
    if not settings.auth_required:
        return "dev-advisor"
    if creds is None:
        raise _unauthorized()
    try:
        claims = jwt.decode(
            creds.credentials, settings.jwt_signing_key, algorithms=["HS256"],  # pin the algorithm
            audience=settings.jwt_audience, issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired")
    except jwt.InvalidTokenError:
        raise _unauthorized()
    if claims.get("role") not in {"advisor", "admin"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return str(claims["sub"])


def require_service(request: Request,
                    creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    settings: Settings = request.app.state.settings
    expected = settings.service_token
    if not expected or creds is None or not hmac.compare_digest(creds.credentials, expected):
        raise _unauthorized()
    return "service"


def check_startup_security(settings: Settings) -> None:
    """Fail closed: refuse to start with unsafe settings."""
    weak = {"", "replace-me", "replace-with-long-random-string"}
    if settings.auth_required and (settings.jwt_signing_key in weak or len(settings.jwt_signing_key) < 32):
        raise RuntimeError(
            "AUTH_REQUIRED=true but JWT_SIGNING_KEY is missing or too short (need 32+ chars). "
            "Fix: run scripts\\setup_env.ps1 from the aurelius folder (it generates one), "
            "or: py -c \"import secrets; print(secrets.token_urlsafe(48))\"")
    if "*" in settings.origins:
        raise RuntimeError("ALLOWED_ORIGINS must not be '*' for an app that uses credentials.")
