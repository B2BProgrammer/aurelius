"""
Compliance rules for OUTPUT (what the AI says to the advisor or a client).

LEARN: Financial communications are regulated (in the US, FINRA Rule 2210
covers communications with the public). Two rules we automate here:
  1. No promissory or exaggerated claims ("guaranteed returns", "risk-free").
  2. Required disclosures, e.g. projections are hypothetical.
Sentinel FIXES outputs instead of blocking them, and says what it changed,
so the advisor still gets an answer and can see why it was edited.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseRule:
    id: str
    pattern: re.Pattern
    description: str


PROMISSORY_RULES: list[PhraseRule] = [
    PhraseRule("CMP_GUARANTEE",
               re.compile(r"\bguarantee(d|s)?\b(?:\s+\w+){0,3}\s+(returns?|income|profits?|gains?|growth|performance)\b"
                          r"|\b(returns?|income|profits?|gains?)\s+(are|is)\s+guaranteed\b", re.I),
               "Guaranteed returns/income"),
    PhraseRule("CMP_NO_RISK",
               re.compile(r"\b(risk[- ]free|no risk|zero risk|without any risk|can(?:no|')t lose|cannot lose|safe bet)\b", re.I),
               "Claims an investment has no risk"),
    PhraseRule("CMP_CERTAINTY",
               re.compile(r"\b(will definitely|certain to|sure to|bound to)\s+(go up|rise|increase|outperform|double|grow)\b", re.I),
               "Predicts market moves with certainty"),
]

REPLACEMENT = "[removed: non-compliant claim]"

ANSWER_DISCLOSURE = (
    "\n\n_For advisor use only. Not investment advice to clients until reviewed. "
    "Projections are hypothetical and not guaranteed._"
)
EMAIL_DISCLOSURE = (
    "\n\nInvestments involve risk, including possible loss of principal. "
    "Past performance and projections do not guarantee future results."
)
_PERFORMANCE_WORDS = re.compile(
    r"\b(returns?|performance|projection|projected|probability|yield|outperform|gains?|growth rate)\b", re.I)


def remove_promissory(text: str) -> tuple[str, list[str]]:
    fired = []
    for rule in PROMISSORY_RULES:
        text, n = rule.pattern.subn(REPLACEMENT, text)
        if n:
            fired.extend([rule.id] * n)
    return text, fired


def add_disclosure(text: str, kind: str) -> tuple[str, str | None]:
    """Returns (text, rule id or None). Never adds the same disclosure twice."""
    if kind == "answer":
        if "For advisor use only" in text:
            return text, None
        return text + ANSWER_DISCLOSURE, "CMP_DISCLOSURE_ANSWER"
    if kind == "email" and _PERFORMANCE_WORDS.search(text):
        if "possible loss of principal" in text:
            return text, None
        return text + EMAIL_DISCLOSURE, "CMP_DISCLOSURE_EMAIL"
    return text, None
