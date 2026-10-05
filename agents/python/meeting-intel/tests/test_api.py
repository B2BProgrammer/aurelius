"""End-to-end tests of the Scribe HTTP API (rules mode, real sample notes)."""
import pytest

from api.app import create_app
from core.config import Settings

from conftest import invoke


def test_health_and_card(client):
    h = client.get("/health").json()
    assert h["agent"] == "scribe" and h["clients_with_notes"] == 3 and h["extraction"] == "rules"
    card = client.get("/.well-known/agent.json").json()
    assert set(card["skills"]) == {"summarize_meetings", "extract_meeting"}


def test_auth_required(client):
    assert client.get("/v1/meetings/patel-001").status_code == 401
    assert client.post("/invoke", json={"skill": "x", "input": {},
                                        "context": {"trace_id": "t", "user_id": "u"}}).status_code == 401


def test_list_meetings(client, auth):
    m = client.get("/v1/meetings/patel-001", headers=auth).json()["meetings"]
    assert [x["date"] for x in m] == ["2026-07-14", "2026-04-10"]
    assert client.get("/v1/meetings/bad id!", headers=auth).status_code == 422


def test_summarize_garcia(client, auth):
    o = invoke(client, auth, "summarize_meetings", client_id="garcia-003")["output"]
    assert o["meetings_found"] == 1
    assert {f["type"] for f in o["compliance_flags"]} >= {"complaint", "client_trade_request",
                                                          "concentration_increase"}
    assert any(a["due"] == "2026-09-20" for a in o["open_action_items"])


def test_summarize_client_from_context(client, auth):
    r = invoke(client, auth, "summarize_meetings", ctx_client="chen-002")
    assert r["status"] == "ok" and r["output"]["last_meeting"] == "2026-06-02"


def test_last_n(client, auth):
    assert invoke(client, auth, "summarize_meetings", client_id="patel-001", last_n=1)["output"]["meetings_found"] == 1


def test_extract_pasted_notes(client, auth):
    notes = ("Quick call with Lin. Lin is worried about rising rates. I will send a bond ladder proposal by "
             "July 1. Lin will send the account statements. They will think about it.")
    o = invoke(client, auth, "extract_meeting", notes=notes, meeting_date="2026-06-10")["output"]
    acts = o["extract"]["action_items"]
    assert o["source"] == "pasted" and acts[0]["due"] == "2026-07-01"
    assert ("client", "Lin to send the account statements") in [(a["owner"], a["task"]) for a in acts]
    assert not any(a["task"].startswith("They") for a in acts)  # pronouns are not names
    assert o["extract"]["client_concerns"]


@pytest.mark.parametrize("skill,inp,err", [
    ("summarize_meetings", {}, "invalid input"),
    ("summarize_meetings", {"client_id": "bad id!"}, "invalid input"),
    ("summarize_meetings", {"client_id": "patel-001", "last_n": 50}, "invalid input: last_n"),
    ("extract_meeting", {"notes": "too short"}, "invalid input: notes"),
    ("extract_meeting", {"notes": "x" * 20001}, "longer than"),
    ("extract_meeting", {"notes": "x" * 30, "meeting_date": "July 1"}, "invalid input: meeting_date"),
    ("delete_notes", {}, "unknown skill"),
])
def test_errors(client, auth, skill, inp, err):
    r = invoke(client, auth, skill, **inp)
    assert r["status"] == "error" and err in r["error"]


def test_refuses_weak_token():
    with pytest.raises(RuntimeError):
        create_app(Settings(_env_file=None, service_token="replace-me"))
