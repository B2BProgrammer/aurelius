"""
PII detection and masking.

LEARN:
  * Order matters. SSNs and card numbers are checked BEFORE the generic
    "long number = account number" rule, so each number gets the most
    specific label.
  * Some patterns need a VALIDATOR, not just a regex. A 16-digit number is
    only a card number if it passes the Luhn checksum; otherwise it's
    probably an account or reference number.
  * We replace PII with a label like [SSN] instead of deleting it, so the
    LLM still understands the sentence ("client SSN is [SSN]").
  * Production systems add ML-based detectors (e.g. Microsoft Presidio) for
    names and addresses. Regex is the fast, explainable first layer.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable


def luhn_ok(number: str) -> bool:
    """Credit-card checksum: double every 2nd digit from the right, sum, mod 10."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass(frozen=True)
class PiiRule:
    id: str            # rule id used in findings and audit, e.g. PII_SSN
    label: str         # what replaces the match, e.g. [SSN]
    pattern: re.Pattern
    description: str
    validator: Callable[[str], bool] | None = None
    group: int = 0     # which regex group to mask (0 = whole match)


PII_RULES: list[PiiRule] = [
    PiiRule("PII_SSN", "SSN",
            re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
            "US Social Security number (123-45-6789)"),
    PiiRule("PII_SSN", "SSN",
            re.compile(r"(?i)\b(?:ssn|social security(?: number)?)\s*(?:is|:|#)?\s*(\d{9})\b"),
            "Unformatted SSN after the word SSN", group=1),
    PiiRule("PII_CARD", "CARD_NUMBER",
            re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
            "Payment card number (Luhn-validated)", validator=luhn_ok),
    PiiRule("PII_DOB", "DATE_OF_BIRTH",
            re.compile(r"(?i)\b(?:dob|date of birth|born on|birth ?date)\s*(?:is|:)?\s*"
                       r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})"),
            "Date of birth (only when labelled as one)", group=1),
    PiiRule("PII_EMAIL", "EMAIL",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
            "Email address"),
    PiiRule("PII_PHONE", "PHONE",
            re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"),
            "US phone number"),
    PiiRule("PII_ACCOUNT", "ACCOUNT_NUMBER",
            # not after $ or a digit group, not before more digits / ",ddd" / ".dd"
            re.compile(r"(?<![\d$,.])\d{8,17}(?!\d|,\d|\.\d)"),
            "Bank/brokerage account number (8-17 digits, not a $ amount)"),
]

SECRET_RULES: list[PiiRule] = [
    PiiRule("SECRET_API_KEY", "SECRET",
            re.compile(r"\b(?:sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
            "API keys and cloud credentials"),
    PiiRule("SECRET_JWT", "SECRET",
            re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
            "Login tokens (JWT)"),
]


def _apply(rules: list[PiiRule], text: str) -> tuple[str, Counter]:
    counts: Counter = Counter()
    for rule in rules:
        def replace(m: re.Match, rule=rule) -> str:
            value = m.group(rule.group)
            if rule.validator and not rule.validator(value):
                return m.group(0)  # looks similar but isn't, leave it
            counts[(rule.id, rule.label)] += 1
            if rule.group == 0:
                return f"[{rule.label}]"
            start, end = m.start(rule.group) - m.start(0), m.end(rule.group) - m.start(0)
            whole = m.group(0)
            return whole[:start] + f"[{rule.label}]" + whole[end:]
        text = rule.pattern.sub(replace, text)
    return text, counts


def mask_pii(text: str) -> tuple[str, Counter]:
    """Returns (masked text, Counter of (rule_id, label) -> count)."""
    return _apply(PII_RULES, text)


def mask_secrets(text: str) -> tuple[str, Counter]:
    return _apply(SECRET_RULES, text)
