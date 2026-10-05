"""
The guard engine: Sentinel's two skills.

  guard_input(text)        advisor's request, BEFORE it reaches any LLM
      1. secrets  -> mask
      2. PII      -> mask
      3. injection score -> allow / ask LLM / block

  guard_output(text, kind) answer or email, BEFORE the advisor sees it
      1. secrets  -> mask
      2. PII      -> mask (catches leaks from agents or the LLM)
      3. promissory claims -> remove
      4. disclosure -> append when required

LEARN: Input checks may BLOCK (refuse the request). Output checks SANITIZE
(fix and explain), because blocking an answer after all the work is done
helps no one, while a fixed answer with notes is safe and useful.
"""
from __future__ import annotations

import logging
from collections import Counter

from core.config import Settings
from guards.compliance import add_disclosure, remove_promissory
from guards.injection import INJECTION_RULES, score_injection
from guards.pii import mask_pii, mask_secrets
from llm.classifier import Classifier
from schemas.models import Finding, GuardResult

log = logging.getLogger("sentinel.engine")

_RULE_DESCRIPTIONS = {r.id: r.description for r in INJECTION_RULES}


def _pii_findings(counts: Counter, category: str) -> tuple[list[Finding], list[str]]:
    findings, notes = [], []
    by_label: Counter = Counter()
    for (rule_id, label), n in counts.items():
        findings.append(Finding(rule=rule_id, category=category, count=n))  # type: ignore[arg-type]
        by_label[label] += n
    for label, n in by_label.items():
        notes.append(f"Masked {label}" + (f" x{n}" if n > 1 else ""))
    return findings, notes


class GuardEngine:
    def __init__(self, settings: Settings, classifier: Classifier):
        self.settings, self.classifier = settings, classifier

    # ------------------------------------------------------------------ input
    async def guard_input(self, text: str) -> GuardResult:
        findings: list[Finding] = []
        notes: list[str] = []

        text, secret_counts = mask_secrets(text)
        f, n = _pii_findings(secret_counts, "secret")
        findings += f
        notes += n

        safe, pii_counts = mask_pii(text)
        f, n = _pii_findings(pii_counts, "pii")
        findings += f
        notes += n

        score, fired = score_injection(text)
        findings += [Finding(rule=r, category="injection") for r in fired]
        llm_checked = False

        if score >= self.settings.injection_block_score:
            reasons = ", ".join(_RULE_DESCRIPTIONS[r] for r in fired)
            return GuardResult(allowed=False, decision="block", text="",
                               notes=["Blocked: possible prompt injection", f"Reason: {reasons}"],
                               findings=findings, injection_score=score)

        if score >= self.settings.injection_review_score:
            verdict = await self.classifier.classify(text)
            llm_checked = verdict is not None
            if verdict and verdict.is_injection and verdict.confidence >= 0.7:
                return GuardResult(allowed=False, decision="block", text="",
                                   notes=["Blocked: possible prompt injection",
                                          f"Reason (AI classifier): {verdict.reason}"],
                                   findings=findings + [Finding(rule="INJ_LLM", category="injection")],
                                   injection_score=score, llm_checked=True)
            if verdict is None:
                notes.append("Flagged for review: unusual instructions in request")
            else:
                notes.append("Checked by AI classifier: not an injection")

        decision = "sanitized" if findings else "allow"
        return GuardResult(allowed=True, decision=decision, text=safe, notes=notes,
                           findings=findings, injection_score=score, llm_checked=llm_checked)

    # ----------------------------------------------------------------- output
    async def guard_output(self, text: str, kind: str) -> GuardResult:
        findings: list[Finding] = []
        notes: list[str] = []

        text, secret_counts = mask_secrets(text)
        f, n = _pii_findings(secret_counts, "secret")
        findings += f
        notes += [f"Leak prevented: {x}" for x in n]

        text, pii_counts = mask_pii(text)
        f, n = _pii_findings(pii_counts, "pii")
        findings += f
        notes += n

        text, promissory = remove_promissory(text)
        if promissory:
            findings += [Finding(rule=r, category="compliance") for r in sorted(set(promissory))]
            notes.append(f"Removed non-compliant claim x{len(promissory)}" if len(promissory) > 1
                         else "Removed non-compliant claim")

        text, disclosure_rule = add_disclosure(text, kind)
        if disclosure_rule:
            findings.append(Finding(rule=disclosure_rule, category="compliance"))
            notes.append("Added disclosure")

        decision = "sanitized" if findings else "allow"
        return GuardResult(allowed=True, decision=decision, text=text, notes=notes, findings=findings)
