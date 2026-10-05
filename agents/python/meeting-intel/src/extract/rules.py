"""
Rule-based extraction: works with NO API key, fully predictable.

LEARN: It's worth comparing this file with extract/llm.py.
  * Rules handle the "tidy" notes well (an "Action items" list with
    "Advisor:" / "Client:" prefixes and "(due YYYY-MM-DD)").
  * On free-form notes, rules catch the common phrasings ("I will...",
    "Anita will...", "worried", "complaint") but miss anything phrased
    differently. That gap is exactly why LLMs are used for extraction.
  * Rules are still valuable as a FALLBACK: when the LLM is down or returns
    invalid output, the advisor still gets something useful.
"""
from __future__ import annotations

import re
from datetime import date

from schemas.models import ActionItem, ComplianceFlag, MeetingExtract

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_ACTION_HEADING = re.compile(r"^#{1,6}\s*action items?\s*$", re.I | re.M)
_ADVISOR_ACTION = re.compile(r"\b(?:I|[Ww]e)\s+(?:will|'ll|need to|must|should)\s+(?:also\s+)?(?P<task>.+)")
_CLIENT_ACTION = re.compile(r"\b(?P<name>[A-Z][a-z]+)\s+(?:will|to|needs to|should)\s+(?:also\s+)?(?P<task>.+)")
_DUE_ISO = re.compile(r"\(?\s*due\s+(\d{4}-\d{2}-\d{2})\s*\)?", re.I)
_DUE_BY = re.compile(r"\bby\s+([A-Z][a-z]+)\s+(\d{1,2})\b")
_NEXT = re.compile(r"[Nn]ext (?:review|meeting)[^.]*?\b(?:for|on|in)\s+([A-Z][a-z]+(?:\s+\d{1,2})?,?\s*\d{4})")

_CONCERN = re.compile(r"\b(worried|worry|concern(ed|s)?|nervous|anxious|uneasy|unhappy|upset)\b", re.I)
_LIFE_EVENTS = [
    (re.compile(r"\bretire", re.I), "Retirement"),
    (re.compile(r"\b(married|wedding)\b", re.I), "Wedding"),
    (re.compile(r"\b(college|university)\b", re.I), "College"),
    (re.compile(r"\b(baby|born|pregnan)", re.I), "New child"),
    (re.compile(r"\bdivorc", re.I), "Divorce"),
    (re.compile(r"\b(passed away|death|died)\b", re.I), "Death in family"),
    (re.compile(r"\binherit", re.I), "Inheritance"),
    (re.compile(r"\bbonus\b", re.I), "Bonus / windfall"),
    (re.compile(r"\b(new job|job change|laid off|promotion)\b", re.I), "Job change"),
    (re.compile(r"\b(buying a (home|house)|new home|home purchase)\b", re.I), "Home purchase"),
]
_NOT_NAMES = {"He", "She", "They", "It", "This", "That", "The", "There", "Advisor", "Client", "Both",
              "Everyone", "Someone", "Nobody", "Next", "Then", "Also", "Market", "Markets"}
_COMPLAINT = re.compile(r"\bcomplain(t|ts|ed|ing)?\b", re.I)
_TRADE_REQUEST = re.compile(r"\b(asked|wants|wanted|told)\s+(me|us)\s+to\s+(buy|sell|move)\b", re.I)


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENT_SPLIT.split(flat) if s.strip()]


def _clean_task(task: str) -> str:
    task = _DUE_ISO.sub("", task).strip().rstrip(".").strip()
    return task[:1].upper() + task[1:]


def _due(text: str, meeting: date | None) -> str | None:
    if m := _DUE_ISO.search(text):
        return m.group(1)
    if (m := _DUE_BY.search(text)) and meeting and m.group(1).lower() in MONTHS:
        month, day = MONTHS[m.group(1).lower()], int(m.group(2))
        year = meeting.year + (1 if month < meeting.month else 0)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def extract_with_rules(text: str, meeting_date: str | None, attendees: str | None) -> MeetingExtract:
    meeting = date.fromisoformat(meeting_date) if meeting_date else None
    client_names = {n.strip().split()[0] for n in (attendees or "").split(",")
                    if n.strip() and "advisor" not in n.lower()}

    # 1. split off an explicit "Action items" section if there is one
    parts = _ACTION_HEADING.split(text, maxsplit=1)
    body, action_section = parts[0], (parts[1] if len(parts) > 1 else "")
    body = re.sub(r"^#{1,6}.*$", "", body, flags=re.M)  # drop other headings
    sentences = _sentences(body)

    actions: list[ActionItem] = []
    for line in action_section.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        owner = "unknown"
        if m := re.match(r"(advisor|client)\s*:\s*", line, re.I):
            owner, line = m.group(1).lower(), line[m.end():]
        actions.append(ActionItem(owner=owner, task=_clean_task(line), due=_due(line, meeting)))

    # 2. free-form sentences: "I will...", "Anita will...", "we need to..."
    for s in sentences:
        if m := _ADVISOR_ACTION.search(s):
            actions.append(ActionItem(owner="advisor", task=_clean_task(m.group("task")), due=_due(s, meeting)))
        elif (m := _CLIENT_ACTION.search(s)) and (
                m.group("name") in client_names                       # known attendee
                or (not client_names and m.group("name") not in _NOT_NAMES)):  # pasted notes: any name
            actions.append(ActionItem(owner="client", task=_clean_task(f"{m.group('name')} to {m.group('task')}"),
                                      due=_due(s, meeting)))

    seen, unique = set(), []
    for a in actions:
        if a.task.lower() not in seen:
            seen.add(a.task.lower())
            unique.append(a)

    concerns = [s for s in sentences if _CONCERN.search(s) and not _COMPLAINT.search(s)]
    life, labels_seen = [], set()
    for s in sentences:
        if _ADVISOR_ACTION.search(s) and not s.lower().startswith(("big news", "news")):
            continue  # "I will model retirement..." is a task, not a new life event
        if _TRADE_REQUEST.search(s):
            continue
        for pattern, label in _LIFE_EVENTS:
            if pattern.search(s) and label not in labels_seen:
                labels_seen.add(label)
                life.append(f"{label}: {s}")
                break

    flags = []
    for s in sentences:
        if _COMPLAINT.search(s):
            flags.append(ComplianceFlag(type="complaint", detail=s))
        if _TRADE_REQUEST.search(s):
            flags.append(ComplianceFlag(type="client_trade_request", detail=s))
            if re.search(r"\bbuy more\b", s, re.I):
                flags.append(ComplianceFlag(type="concentration_increase", detail=s))

    next_meeting = m.group(1) if (m := _NEXT.search(re.sub(r"\s+", " ", text))) else None
    summary = " ".join(sentences[:2]) if sentences else "(no discussion text)"

    return MeetingExtract(summary=summary[:800], action_items=unique, client_concerns=concerns,
                          life_events=life, compliance_flags=flags, next_meeting=next_meeting)
