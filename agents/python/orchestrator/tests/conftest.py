"""
Shared test setup.

LEARN: Tests build Settings directly (ignoring your .env), with the fake LLM
and fake agents, so they're fast, free and give the same result every time.
"""
import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from api.app import create_app
from security.auth import create_token


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_mock=True,
        mock_agents=True,
        auth_required=True,
        jwt_signing_key="test-signing-key-that-is-long-enough-123456",
        service_token="test-service-token-123456",
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:  # "with" runs startup/shutdown
        yield c


@pytest.fixture
def auth(settings) -> dict:
    return {"Authorization": f"Bearer {create_token(settings, 'advisor-007')}"}
