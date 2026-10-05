"""
Mask PII BEFORE meeting notes are sent to the LLM.

LEARN: Defense in depth. Sentinel masks PII in the advisor's chat message,
but these notes come from storage and never pass through Sentinel. So the
Scribe applies the same principle itself: the LLM only receives what it
needs. A model can summarize "Raj gave his SSN [SSN]" just as well, and the
real number never leaves our systems.

(This is a compact version of Sentinel's rules. In production, all agents
would call one shared redaction library or Sentinel itself.)
"""
from __future__ import annotations

import re

_RULES = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\d)\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")),
    ("ACCOUNT_NUMBER", re.compile(r"(?<![\d$,.])\d{8,17}(?!\d|,\d|\.\d)")),
]


def mask(text: str) -> tuple[str, list[str]]:
    found = []
    for label, pattern in _RULES:
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            found.append(label)
    return text, found
