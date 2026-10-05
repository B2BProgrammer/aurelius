"""Unit tests: redaction, rule-based extraction, and the validated Claude path."""
import asyncio

from core.config import Settings
from extract.redact import mask
from extract.rules import extract_with_rules
from extract.service import Scribe
from notes.store import NotesStore

from conftest import FakeClaude

FREE_FORM = """Call with Raj and Anita. Raj wants to retire at 62. Their daughter is getting married next June.
Raj said he is worried about XYZ. I will model retirement at 62 and send it by August 15.
Anita will email me the wedding budget. Raj asked me to sell half of XYZ. Next review scheduled for October 2026."""


def test_mask_removes_pii():
    text, found = mask("SSN 123-45-6789, email raj@example.com, acct 123456789012.")
    assert "6789" not in text and set(found) == {"SSN", "EMAIL", "ACCOUNT_NUMBER"}


def test_rules_on_free_form_notes():
    e = extract_with_rules(FREE_FORM, "2026-07-14", "Raj Patel, Anita Patel, Advisor")
    owners = {(a.owner, a.task.split()[0]) for a in e.action_items}
    assert ("advisor", "Model") in owners and ("client", "Anita") in owners
    model_task = next(a for a in e.action_items if a.task.startswith("Model"))
    assert model_task.due == "2026-08-15"                       # "by August 15" -> ISO date
    assert any("worried" in c for c in e.client_concerns)
    assert {l.split(":")[0] for l in e.life_events} == {"Retirement", "Wedding"}
    assert [f.type for f in e.compliance_flags] == ["client_trade_request"]
    assert e.next_meeting == "October 2026"


def test_rules_on_structured_action_list():
    notes = "## Discussion\nAll good.\n\n## Action items\n- Advisor: send RMD estimate (due 2027-01-15)\n- Client: sign forms"
    e = extract_with_rules(notes, "2026-06-02", "Wei Chen, Advisor")
    assert [(a.owner, a.task, a.due) for a in e.action_items] == [
        ("advisor", "Send RMD estimate", "2027-01-15"), ("client", "Sign forms", None)]


def test_complaint_and_concentration_flags():
    e = extract_with_rules("Luis asked me to buy more ABC. Maria wants to file a complaint.", "2026-09-05",
                           "Maria Garcia, Luis Garcia, Advisor")
    assert {f.type for f in e.compliance_flags} == {"client_trade_request", "concentration_increase", "complaint"}


def test_summarize_patel_from_stored_notes(settings):
    r = asyncio.run(Scribe(settings, NotesStore(settings.notes_dir)).summarize("patel-001", None))
    assert r.meetings_found == 2 and r.last_meeting == "2026-07-14"
    assert any("retire" in a.task.lower() for a in r.open_action_items)
    assert any(f.type == "pii_in_notes" for f in r.compliance_flags)     # the SSN in the July notes
    assert all("123-45-6789" not in m.extract.summary for m in r.meetings)


def test_unknown_client_has_no_meetings(settings):
    r = asyncio.run(Scribe(settings, NotesStore(settings.notes_dir)).summarize("nobody-1", None))
    assert r.meetings_found == 0 and r.open_action_items == []


# ------------------------------------------------------------- the Claude path
GOOD = {"summary": "Raj plans to retire at 62.", "action_items": [{"owner": "advisor", "task": "Model retirement",
        "due": "2026-08-15"}], "client_concerns": ["XYZ concentration"], "life_events": ["Retirement at 62"],
        "compliance_flags": [], "next_meeting": "October 2026"}


def test_claude_path_used_and_pii_never_sent(settings):
    fake = FakeClaude(GOOD)
    s = Scribe(Settings(_env_file=None, service_token="x" * 30), NotesStore(settings.notes_dir), llm_client=fake)
    r = asyncio.run(s.extract_one("Raj gave SSN 123-45-6789. " + FREE_FORM, "2026-07-14", "Raj Patel, Advisor"))
    assert r.extracted_by.startswith("claude") and r.extract.summary == "Raj plans to retire at 62."
    assert "123-45-6789" not in fake.sent[0] and "[SSN]" in fake.sent[0]      # masked BEFORE the LLM
    assert any(f.type == "pii_in_notes" for f in r.extract.compliance_flags)  # added by code


def test_invalid_claude_output_falls_back_to_rules(settings):
    bad = {**GOOD, "action_items": [{"owner": "the intern", "task": "x"}]}  # owner not allowed
    s = Scribe(Settings(_env_file=None, service_token="x" * 30), NotesStore(settings.notes_dir),
               llm_client=FakeClaude(bad))
    r = asyncio.run(s.extract_one(FREE_FORM, "2026-07-14", "Raj Patel, Anita Patel, Advisor"))
    assert r.extracted_by == "rules (LLM fallback)" and r.extract.action_items


def test_cache_avoids_second_llm_call(settings):
    fake = FakeClaude(GOOD)
    s = Scribe(Settings(_env_file=None, service_token="x" * 30), NotesStore(settings.notes_dir), llm_client=fake)
    asyncio.run(s.extract_one(FREE_FORM, "2026-07-14", None))
    asyncio.run(s.extract_one(FREE_FORM, "2026-07-14", None))
    assert len(fake.sent) == 1
