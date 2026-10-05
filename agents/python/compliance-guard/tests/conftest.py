"""
Shared test setup: Settings built in code (ignores your .env), no real LLM,
and the audit log written to a temporary folder.
"""
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import Settings
from llm.classifier import NoClassifier, Verdict

SERVICE_TOKEN = "test-service-token-abcdefghijklmnop"


class FakeClassifier:
    """Pretends to be Claude: says 'injection' when the text contains 'pirate'."""

    def __init__(self):
        self.calls = 0

    async def classify(self, text):
        self.calls += 1
        if "pirate" in text.lower():
            return Verdict(True, 0.95, "Asks the assistant to abandon its role")
        return Verdict(False, 0.9, "Ordinary request")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, service_token=SERVICE_TOKEN, llm_mock=True,
                    audit_log_path=str(tmp_path / "audit.jsonl"))


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings, classifier=NoClassifier())) as c:
        yield c


@pytest.fixture
def auth() -> dict:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def invoke_body(skill: str, text: str, kind: str = "answer") -> dict:
    return {"skill": skill, "input": {"text": text, "kind": kind},
            "context": {"trace_id": "test-trace", "user_id": "advisor-007"}}
