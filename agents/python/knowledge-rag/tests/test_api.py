"""End-to-end tests of the Librarian HTTP API (hash embeddings, no LLM)."""
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.config import Settings
from llm.answerer import NOT_FOUND
from rag.store import Hit

from conftest import ask


def test_health_shows_index(client):
    h = client.get("/health").json()
    assert h["agent"] == "librarian" and h["chunks_indexed"] > 20 and h["embeddings"] == "hash"


def test_agent_card(client):
    card = client.get("/.well-known/agent.json").json()
    assert "search_knowledge" in card["skills"]
    assert "query" in card["skills"]["search_knowledge"]["input_schema"]["properties"]


def test_auth_required(client):
    body = {"skill": "search_knowledge", "input": {"query": "x"}, "context": {"trace_id": "t", "user_id": "u"}}
    assert client.post("/invoke", json=body).status_code == 401
    assert client.get("/v1/documents").status_code == 401
    assert client.post("/v1/ingest").status_code == 401


def test_grounded_answer_with_citations(client, auth):
    r = ask(client, auth, "How does the wash sale rule work?")
    out = r["output"]
    assert r["status"] == "ok" and out["grounded"] and out["answered_by"] == "extractive"
    assert out["citations"][0]["source"] == "tax-loss-harvesting.md"
    assert "[1]" in out["answer"] and "30 days" in out["answer"]


def test_not_found_instead_of_guessing(client, auth):
    out = ask(client, auth, "What is the capital of France?")["output"]
    assert out["grounded"] is False and out["answer"] == NOT_FOUND and out["citations"] == []


def test_conductor_extra_fields_are_ignored(client, auth):
    r = ask(client, auth, "RMD age", client_id="patel-001", prior_results={"pulse.get_events": {}})
    assert r["status"] == "ok"


def test_doc_type_filter(client, auth):
    out = ask(client, auth, "XYZ concentration", doc_type="policy")["output"]
    assert all(c["source"] == "concentration-policy.md" or "policy" in c["source"] for c in out["citations"])


@pytest.mark.parametrize("inp,err", [
    ({}, "invalid input: query"),
    ({"query": ""}, "invalid input: query"),
    ({"query": "x", "top_k": 50}, "invalid input: top_k"),
    ({"query": "x", "doc_type": "gossip"}, "invalid input: doc_type"),
    ({"query": "x" * 2001}, "longer than"),
])
def test_bad_input(client, auth, inp, err):
    body = {"skill": "search_knowledge", "input": inp, "context": {"trace_id": "t", "user_id": "u"}}
    r = client.post("/invoke", headers=auth, json=body).json()
    assert r["status"] == "error" and err in r["error"]


def test_unknown_skill(client, auth):
    body = {"skill": "delete_index", "input": {}, "context": {"trace_id": "t", "user_id": "u"}}
    assert "unknown skill" in client.post("/invoke", headers=auth, json=body).json()["error"]


def test_raw_search_shows_scores(client, auth):
    r = client.post("/v1/search", headers=auth, json={"query": "expense ratio bond fund", "top_k": 3}).json()
    assert r["results"][0]["source"] == "intl-bond-fund-factsheet.md"
    assert r["results"][0]["passes_cutoff"] is True and 0 < r["results"][0]["score"] <= 1


def test_documents_and_quarantine(client, auth):
    d = client.get("/v1/documents", headers=auth).json()
    assert "concentration-policy.md" in d["documents"]
    assert "vendor-market-note.md" not in d["documents"]  # its only section was quarantined
    assert d["quarantined_last_ingest"][0]["source"] == "vendor-market-note.md"


def test_reingest(client, auth):
    before = client.get("/health").json()["chunks_indexed"]
    report = client.post("/v1/ingest", headers=auth).json()
    assert report["chunks"] == before and report["documents"] >= 8


def test_claude_citations_are_validated(settings):
    """If Claude cites [9] but only 2 passages exist, [9] is removed."""
    from llm.answerer import Answerer

    class FakeBlock:
        type, text = "text", "Limit is 10 percent [1]. Also see [9]."

    class FakeResp:
        content = [FakeBlock()]
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()

    class FakeClient:
        class messages:
            @staticmethod
            async def create(**kw):
                return FakeResp()

    import asyncio
    a = Answerer(settings)
    a.client = FakeClient()
    meta = {"title": "T", "source": "s.md", "section": "S", "effective_date": "d"}
    hits = [Hit("1", "T > S\nLimit 10 percent", meta, 0.9), Hit("2", "T > S2\nOther", {**meta, "section": "S2"}, 0.5)]
    res = asyncio.run(a.answer("limit?", hits))
    assert "[9]" not in res.answer and [c.ref for c in res.citations] == [1]


def test_refuses_weak_token(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(Settings(_env_file=None, service_token="replace-me", chroma_dir=tmp_path))
