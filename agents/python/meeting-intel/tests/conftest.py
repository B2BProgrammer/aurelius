"""
Shared test setup: real sample notes, no API key (rules), plus a fake Claude
for testing the LLM path and its validation.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import Settings

SERVICE_TOKEN = "test-service-token-abcdefghijklmnop"


class FakeClaude:
    """Returns a fixed tool_use payload and records what text it was sent."""

    def __init__(self, payload: dict):
        self.payload, self.sent = payload, []
        self.messages = SimpleNamespace(create=self.create)

    async def create(self, **kw):
        self.sent.append(kw["messages"][0]["content"])
        block = SimpleNamespace(type="tool_use", name="record_meeting", input=self.payload)
        return SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=1, output_tokens=1))


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, service_token=SERVICE_TOKEN, llm_mock=True)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def auth() -> dict:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def invoke(client, auth, skill, ctx_client=None, **inp) -> dict:
    body = {"skill": skill, "input": inp,
            "context": {"trace_id": "test", "user_id": "advisor-007", "client_id": ctx_client}}
    return client.post("/invoke", headers=auth, json=body).json()
