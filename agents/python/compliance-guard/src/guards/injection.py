"""
Prompt-injection detection.

LEARN: Defense in layers.
  Layer 1 (here): fast rules. Each rule has a weight; scores combine like
                  probabilities: 1 - (1-a)(1-b)... More signals = higher score.
  Layer 2 (engine.py): if the score is borderline, ask a small LLM (Haiku)
                  for a second opinion. Cheap because it runs only sometimes.
  Layer 3 (Conductor): the user's text is wrapped in <request> tags and
                  treated as data, so even a missed attack is less effective.

Before matching we NORMALIZE the text: lowercase, remove invisible
characters, collapse spaces. Attackers use tricks like "Ig​nore
prev​ious" (zero-width spaces) to slip past naive regexes.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionRule:
    id: str
    weight: float
    pattern: re.Pattern
    description: str


def _r(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


INJECTION_RULES: list[InjectionRule] = [
    InjectionRule("INJ_OVERRIDE", 0.9,
                  _r(r"\b(ignore|disregard|forget|override|bypass)\b.{0,30}\b(previous|prior|above|earlier|all|your|the|system)\b"
                     r".{0,20}\b(instructions?|rules|prompts?|guidelines|directions)\b"),
                  "Tries to cancel the system's instructions"),
    InjectionRule("INJ_PROMPT_LEAK", 0.9,
                  _r(r"\b(reveal|show|print|repeat|display|output|leak|tell me)\b.{0,30}"
                     r"\b(system prompt|hidden prompt|initial prompt|your instructions|your rules|your prompt)\b"),
                  "Tries to extract the system prompt"),
    InjectionRule("INJ_ROLE_HIJACK", 0.8,
                  _r(r"\b(you are now|from now on you are|act as|pretend (to be|you are)|switch to)\b.{0,40}"
                     r"\b(developer mode|dan|jailbreak|unrestricted|unfiltered|no restrictions|evil)\b"),
                  "Tries to give the model a new, unrestricted role"),
    InjectionRule("INJ_DEV_MODE", 0.6,
                  _r(r"\b(developer mode|jailbreak|dan mode|god mode)\b"),
                  "Mentions a known jailbreak mode"),
    InjectionRule("INJ_ROLE_SPOOF", 0.5,
                  _r(r"(^|\n)\s*(system|assistant)\s*:|<\s*/?\s*(system|instructions?)\s*>|\[\s*system\s*\]|###\s*(system|instruction)"),
                  "Fake 'system:' or <system> tags inside user text"),
    InjectionRule("INJ_COMPLIANCE_BYPASS", 0.7,
                  _r(r"\b(skip|bypass|disable|turn off|without)\b.{0,20}\b(compliance|approval|review|guardrails?|safety|sentinel|disclosures?)\b"),
                  "Tries to skip compliance or human approval"),
    InjectionRule("INJ_EXFIL", 0.6,
                  _r(r"\b(send|email|forward|upload|post)\b.{0,40}\b(all|every|entire)\b.{0,20}\b(clients?|accounts?|records|data)\b"),
                  "Tries to bulk-export client data"),
    InjectionRule("INJ_ENCODED", 0.3,
                  re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
                  "Long encoded blob (could hide instructions)"),
]

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()


def score_injection(text: str) -> tuple[float, list[str]]:
    """Returns (score 0..1, ids of rules that fired)."""
    norm = normalize(text)
    fired: list[str] = []
    remaining = 1.0
    for rule in INJECTION_RULES:
        target = norm if rule.id != "INJ_ROLE_SPOOF" else text  # spoofing needs line breaks
        if rule.pattern.search(target):
            fired.append(rule.id)
            remaining *= (1 - rule.weight)
    return round(1 - remaining, 3), fired
