"""
Shared test setup.

LEARN: Tests use the offline "hash" embeddings and a temporary Chroma folder,
so they run in seconds, need no download or API key, and never touch your
real index in aurelius\\rag\\chroma-store.
"""
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import REPO_ROOT, Settings

SERVICE_TOKEN = "test-service-token-abcdefghijklmnop"
SAMPLE_DOCS = REPO_ROOT / "rag" / "data" / "sample-docs"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(_env_file=None, service_token=SERVICE_TOKEN, llm_mock=True,
                    embedding_provider="hash", docs_dir=SAMPLE_DOCS, chroma_dir=tmp_path / "chroma")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:  # startup auto-ingests the sample docs
        yield c


@pytest.fixture
def auth() -> dict:
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}


def ask(client, auth, query, **extra) -> dict:
    body = {"skill": "search_knowledge", "input": {"query": query, **extra},
            "context": {"trace_id": "test-trace", "user_id": "advisor-007"}}
    return client.post("/invoke", headers=auth, json=body).json()
