"""
Audit log: a permanent record of every security decision.

LEARN: Regulated firms must be able to answer "why did the system do that?"
months later. Each decision is one JSON line in logs/audit.jsonl:
who, when, which rules fired, what was decided.

What we DON'T store: the text itself (it may contain PII). Instead we store
a SHA-256 fingerprint. If an incident happens, you can prove whether a given
message was the one checked (same fingerprint) without the log becoming a
second copy of client data.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()  # one writer at a time, no interleaved lines

    @staticmethod
    def fingerprint(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def record(self, *, trace_id: str, user_id: str, skill: str, kind: str, decision: str,
               rules: list[str], text: str, injection_score: float, llm_checked: bool,
               duration_ms: int) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "user_id": user_id,
            "skill": skill,
            "kind": kind,
            "decision": decision,
            "rules": rules,
            "injection_score": injection_score,
            "llm_checked": llm_checked,
            "text_sha256": self.fingerprint(text),
            "text_chars": len(text),
            "duration_ms": duration_ms,
        }
        line = json.dumps(entry)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
