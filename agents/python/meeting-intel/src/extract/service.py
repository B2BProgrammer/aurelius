"""
The Scribe's two skills, built from the pieces:

    notes ─> mask PII ─> Claude (validated) ──ok──> MeetingExtract
                            │ no key / failed / invalid
                            └──────> rules ───────> MeetingExtract
                         + code adds a "pii_in_notes" flag if PII was found

LEARN: a small CACHE keyed by a hash of the notes text means re-reading the
same stored meeting never pays for a second LLM call. Edit the notes and the
hash changes, so it's extracted again.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

from core.config import Settings
from extract.llm import ClaudeExtractor
from extract.redact import mask
from extract.rules import extract_with_rules
from notes.store import NotesStore
from schemas.models import ActionItem, ComplianceFlag, MeetingResult, SummarizeResult

log = logging.getLogger("scribe.service")


class Scribe:
    def __init__(self, settings: Settings, store: NotesStore, llm_client=None):
        self.settings, self.store = settings, store
        self.llm = ClaudeExtractor(settings, llm_client) if (settings.use_llm or llm_client) else None
        self._cache: dict[str, MeetingResult] = {}
        if self.llm is None:
            log.warning("No API key (or LLM_MOCK=true): using RULE-BASED extraction")

    async def extract_one(self, text: str, meeting_date: str | None, attendees: str | None,
                          meeting_type: str | None = None, source: str | None = None) -> MeetingResult:
        key = hashlib.sha256(f"{bool(self.llm)}|{meeting_date}|{text}".encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]

        safe_text, pii = mask(text)                     # the LLM never sees raw PII
        extract, by = None, "rules"
        if self.llm:
            extract = await self.llm.extract(safe_text, meeting_date, attendees)
            by = self.settings.llm_model if extract else "rules (LLM fallback)"
        if extract is None:
            extract = extract_with_rules(safe_text, meeting_date, attendees)

        if pii:  # added by CODE, so it never depends on the model noticing
            extract.compliance_flags.append(ComplianceFlag(
                type="pii_in_notes",
                detail=f"Notes contained {', '.join(pii)}. Keep sensitive data in secure CRM fields, not in notes."))

        result = MeetingResult(date=meeting_date, type=meeting_type, source=source,
                               extract=extract, extracted_by=by, pii_masked=pii)
        self._cache[key] = result
        return result

    async def summarize(self, client_id: str, last_n: int | None) -> SummarizeResult:
        meetings = self.store.meetings(client_id, last_n or self.settings.max_meetings)
        results = await asyncio.gather(*(
            self.extract_one(m.text, m.date, m.attendees, m.type, m.source) for m in meetings))

        actions: list[ActionItem] = []
        concerns: list[str] = []
        life: list[str] = []
        flags: list[ComplianceFlag] = []
        seen: set[str] = set()
        for r in results:  # newest first
            for a in r.extract.action_items:
                if a.task.lower() not in seen:
                    seen.add(a.task.lower())
                    actions.append(a)
            concerns += [c for c in r.extract.client_concerns if c not in concerns]
            life += [e for e in r.extract.life_events if e not in life]
            flags += r.extract.compliance_flags

        return SummarizeResult(
            client_id=client_id, meetings_found=len(results),
            last_meeting=results[0].date if results else None,
            summary=results[0].extract.summary if results else "No meeting notes found for this client.",
            open_action_items=actions, client_concerns=concerns, life_events=life,
            compliance_flags=flags, meetings=results)
