"""
Ingest-time safety: refuse to index passages that contain instructions to the AI.

LEARN: "Indirect prompt injection" is the RAG-specific attack. The attacker
doesn't talk to the assistant. They plant instructions inside a DOCUMENT
(a vendor PDF, a web page, an email) and wait for the assistant to retrieve
it. Sentinel never sees it, because it isn't in the user's request.

Two defenses here:
  1. Quarantine at ingest: chunks that look like instructions are never stored.
  2. At answer time (llm/answerer.py) passages are wrapped in <document> tags
     and the model is told to treat them as data, never as instructions.
"""
from __future__ import annotations

import re
import unicodedata

_PATTERNS = [
    (re.compile(r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|all|earlier)\b.{0,20}"
                r"\b(instructions?|rules|prompts?)\b", re.I), "Tries to override the assistant's instructions"),
    (re.compile(r"\b(you are now|from now on you are|act as|pretend to be)\b", re.I),
     "Tries to change the assistant's role"),
    (re.compile(r"\b(system prompt|hidden prompt|your instructions)\b", re.I), "Mentions the assistant's prompt"),
    (re.compile(r"\b(tell|instruct|advise) (every|all) (advisors?|clients?|users?)\b", re.I),
     "Gives orders to the assistant's audience"),
]
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def check_chunk(text: str) -> str | None:
    """Returns a reason if the chunk must be quarantined, else None."""
    norm = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).translate(_INVISIBLE))
    for pattern, reason in _PATTERNS:
        if pattern.search(norm):
            return reason
    return None
