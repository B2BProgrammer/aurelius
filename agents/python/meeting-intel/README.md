# 📝 Scribe — meeting-intel

| Field | Value |
|---|---|
| Codename | Scribe |
| Code ID | `scribe` |
| Language | Python 3.11+ (FastAPI) |
| Port | 8003 |
| Data | Meeting notes in `data\meetings\<client_id>\*.md` (stands in for CRM notes / call transcripts) |
| LLM | Optional: Claude does structured extraction; without a key, rules do |
| Called by | Conductor (`summarize_meetings`) |
| Auth | `Bearer SERVICE_TOKEN` |

## What the Scribe does

Advisors take notes in every client meeting: some tidy, most not. Important things get buried: *"Raj wants to retire at 62"*, *"Anita will email me by August 15"*, *"Maria wants to file a complaint"*.

The Scribe turns notes into a **structured record**:

| Field | Patel, July 2026 |
|---|---|
| `summary` | Mid-year call. Raj now wants to retire at 62 instead of 64… |
| `action_items` | **advisor**: model retirement at 62 and 63 · **advisor**: prepare options for reducing XYZ · **client**: Anita to email the wedding cash amount, due **2026-08-15** |
| `client_concerns` | Worried about tech/XYZ exposure · nervous about taxes on selling XYZ |
| `life_events` | Retirement at 62 · daughter's wedding June 2027 |
| `compliance_flags` | **pii_in_notes**: the notes contained an SSN |
| `next_meeting` | October 2026 |

And for Garcia it raises the flags a compliance officer must see: a **complaint** threat, a **client trade request**, and a request that would **increase a concentrated position** (buy more ABC at 22%).

## How it works

```
 notes ──▶ mask PII ──▶ Claude ──▶ validate against MeetingExtract ──ok──▶ record
 (file or     (SSN →     forced        (pydantic: types, allowed       │
  pasted)      [SSN])    tool call      owners, lengths)               │ invalid / no key / error
                                                                       ▼
                                                      rule-based extractor ──▶ record
                                     + code adds "pii_in_notes" if PII was found
                                     + cache: same notes are never sent to the LLM twice
```

## The new idea in this agent: structured extraction

1. **One schema, three uses**: `MeetingExtract` (in `schemas/models.py`) is (a) the JSON schema Claude must fill, (b) the validator for what Claude returns, and (c) the shape the rule-based fallback produces.
2. **Forced tool call**: Claude must answer by calling `record_meeting` with that schema, never with free text.
3. **Validate, don't trust**: if Claude's output breaks the schema, it's rejected and the rules take over.
4. **Code adds what must never be missed**: the `pii_in_notes` flag comes from code, not from hoping the model notices.

Compare `extract/rules.py` with `extract/llm.py`: rules catch the common phrasings and are perfectly predictable; Claude catches everything else ("Wei turns 73 next year and asked about RMDs" is a life event rules miss). Production systems often run both.

## Skills

| Skill | Input | Use |
|---|---|---|
| `summarize_meetings` | `client_id`, optional `last_n` (1–10) | Before a review: everything from recent meetings in one view (what the Conductor calls) |
| `extract_meeting` | `notes` (pasted text), optional `meeting_date` | Right after a meeting: paste notes or a transcript, get the structured record |

## Folder map

```
meeting-intel/
├── src/
│   ├── main.py             ▶ ENTRY POINT: python src\main.py  (port 8003)
│   ├── extract/            ★ the brain
│   │   ├── service.py        chooses Claude or rules, caching, merges meetings (start here)
│   │   ├── llm.py            Claude structured extraction + validation
│   │   ├── rules.py          rule-based extraction (no key needed)
│   │   └── redact.py         mask PII before the LLM
│   ├── notes/store.py      reads data\meetings\<client>\*.md
│   ├── schemas/models.py   contract + MeetingExtract (the extraction schema)
│   ├── api/app.py          endpoints
│   ├── security/auth.py    service token
│   └── core/               settings, logging
├── data/meetings/          sample notes: patel-001 (2), chen-002 (1), garcia-003 (1)
├── tests/                  24 tests (rules + fake Claude)
├── api-tests.http
└── TESTING.md
```

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Alive + clients with notes + extraction mode (`rules` or the model) |
| GET | `/.well-known/agent.json` | none | Agent card + schemas |
| POST | `/invoke` | service | `summarize_meetings` / `extract_meeting` |
| GET | `/v1/meetings/{client_id}` | service | Which stored meetings exist |

## Security principles in this agent

1. **Data minimization**: PII masked *before* any LLM call. These notes never pass through Sentinel, so the Scribe protects them itself (defense in depth).
2. **Validate LLM output**: schema-checked; invalid output falls back to rules.
3. **Compliance by code**: complaint, trade-request and PII flags surface automatically for supervision.
4. **Untrusted text stays data**: notes go inside `<notes>` tags; instructions inside them are ignored.
5. **Size limits**: notes over 20,000 characters are rejected.
6. **Cost control**: cached extraction, small model.
