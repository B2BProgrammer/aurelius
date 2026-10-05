"""The endpoints for the web and mobile apps (api/apps.py), with the recorded agent answers."""
import pytest
from fastapi.testclient import TestClient

from api import apps
from api.app import create_app
from core.config import Settings
from schemas.models import AgentResponse


@pytest.fixture
def login_client(settings):
    s = settings.model_copy(update={"dev_login_password": "demo-password-123"})
    apps._throttle.fails.clear()
    with TestClient(create_app(s)) as c:
        yield c


# ------------------------------------------------------------------ sign-in
def test_login_issues_a_working_token(login_client):
    r = login_client.post("/v1/auth/login", json={"username": "sam.rivera", "password": "demo-password-123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = login_client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json() == {"user": "sam.rivera", "role": "advisor"}


def test_login_is_throttled_after_5_failures(login_client):
    for _ in range(5):
        assert login_client.post("/v1/auth/login", json={"username": "x1", "password": "nope"}).status_code == 401
    r = login_client.post("/v1/auth/login", json={"username": "x1", "password": "demo-password-123"})
    assert r.status_code == 429  # even the right password waits now


def test_login_disabled_without_password(client):
    assert client.post("/v1/auth/login", json={"username": "sam", "password": "x"}).status_code == 404


def test_app_endpoints_need_a_token(client):
    for path in ["/v1/me", "/v1/clients", "/v1/clients/patel-001/overview", "/v1/stream"]:
        assert client.get(path).status_code == 401, path
    assert client.post("/v1/skills/actuary/risk_score", json={"input": {}}).status_code == 401


# ------------------------------------------------------------------ clients
def test_client_list(client, auth):
    ids = {c["client_id"] for c in client.get("/v1/clients", headers=auth).json()}
    assert ids == {"patel-001", "chen-002", "garcia-003"}


def test_overview_calls_six_agents_in_parallel(client, auth):
    r = client.get("/v1/clients/patel-001/overview", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert set(body["sections"]) == {"household", "portfolio", "kyc", "risk", "events", "meetings"}
    assert all(s["status"] == "ok" for s in body["sections"].values())
    assert body["sections"]["kyc"]["output"]["status"] == "action_needed"
    assert body["sections"]["risk"]["output"]["band"] == "Moderate growth"
    assert body["trace_id"] == r.headers["X-Trace-Id"]
    # parallel: total time ~ one mock call (50 ms), not six
    assert max(s["duration_ms"] for s in body["sections"].values()) < 1000


def test_overview_unknown_client_and_bad_id(client, auth):
    assert client.get("/v1/clients/nobody-1/overview", headers=auth).status_code == 404
    assert client.get("/v1/clients/bad%20id!/overview", headers=auth).status_code == 422


def test_overview_survives_one_agent_down(client, auth):
    from agents import mock_agents

    async def notary_down(agent, req):
        if agent == "notary":
            return AgentResponse(agent=agent, status="error", error="unavailable (ConnectError)")
        return await mock_agents.respond(agent, req)
    client.app.state.agent_client.mock_responder = notary_down
    body = client.get("/v1/clients/garcia-003/overview", headers=auth).json()
    assert body["sections"]["kyc"]["status"] == "error"
    assert body["sections"]["household"]["status"] == "ok"


# ------------------------------------------------------------------ skills allowlist
def test_allowlisted_skill_runs(client, auth):
    r = client.post("/v1/skills/actuary/project_retirement", headers=auth,
                    json={"input": {"client_id": "patel-001", "retire_ages": [62, 63]}})
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["output"]["headline"].startswith("Retire at 62")


def test_writes_and_unknown_skills_are_refused(client, auth):
    for agent, skill in [("liaison", "log_note"), ("notary", "record_document"), ("notary", "screen_name"),
                         ("sentinel", "guard_input"), ("liaison", "drop_tables")]:
        r = client.post(f"/v1/skills/{agent}/{skill}", headers=auth, json={"input": {"client_id": "patel-001"}})
        assert r.status_code == 403, (agent, skill)


def test_skill_input_is_checked(client, auth):
    r = client.post("/v1/skills/notary/check_kyc", headers=auth, json={"input": {"client_id": "../etc"}})
    assert r.status_code == 422
    r = client.post("/v1/skills/librarian/search_knowledge", headers=auth, json={"input": {"query": "x" * 9000}})
    assert r.status_code == 413


def test_model_written_text_goes_through_sentinel(client, auth):
    r = client.post("/v1/skills/librarian/search_knowledge", headers=auth,
                    json={"input": {"query": "concentration policy"}})
    assert "Added disclosure" in r.json()["guardrail_notes"]


# ------------------------------------------------------------------ draft approval
def test_approving_a_draft_logs_a_crm_note(client, auth):
    seen = {}
    from agents import mock_agents

    async def spy(agent, req):
        seen[(agent, req.skill)] = req.input
        return await mock_agents.respond(agent, req)
    client.app.state.agent_client.mock_responder = spy
    r = client.post("/v1/drafts/approve", headers=auth, json={
        "client_id": "patel-001", "subject": "Following up",
        "body": "Hi Raj and Anita,\n\nThanks for meeting today.\n\nSam"})
    assert r.status_code == 200 and r.json()["approved"] is True
    note = seen[("liaison", "log_note")]
    assert note["type"] == "email" and "Following up" in note["note"]
    assert "Thanks for meeting" not in note["note"]  # the CRM gets subject + fingerprint, not the body


def test_approval_refused_if_sentinel_changes_the_text(client, auth):
    r = client.post("/v1/drafts/approve", headers=auth, json={
        "client_id": "patel-001", "subject": "Your SSN",
        "body": "Hi Raj,\n\nYour SSN 123-45-6789 is on file now.\n\nSam"})
    body = r.json()
    assert body["approved"] is False and "123-45-6789" not in body["revised_body"]


# ------------------------------------------------------------------ stream
def test_stream_says_hello_pings_and_ends_at_its_time_limit(client, auth, monkeypatch):
    monkeypatch.setattr(apps, "HEARTBEAT_S", 0.05)
    monkeypatch.setattr(apps, "STREAM_MAX_S", 0.3)
    with client.stream("GET", "/v1/stream?client_id=garcia-003", headers=auth) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        lines = list(r.iter_lines())
    assert lines[0] == "event: hello"
    assert ": ping" in lines
    assert "event: bye" in lines


def test_cors_allows_the_web_app(client):
    r = client.options("/v1/clients", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET",
                                               "Access-Control-Request-Headers": "authorization"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    evil = client.options("/v1/clients", headers={"Origin": "https://evil.example",
                                                  "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in evil.headers


def test_settings_default_to_ipv4_loopback():
    s = Settings(_env_file=None)
    assert s.conductor_host == "127.0.0.1"
    assert all(u.startswith("http://127.0.0.1:") for u in
               [s.sentinel_url, s.librarian_url, s.herald_url, s.notary_url, s.pulse_url])
