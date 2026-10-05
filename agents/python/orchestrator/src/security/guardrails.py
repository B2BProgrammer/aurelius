"""
Guardrails: every request and every answer passes through Sentinel.

LEARN: "Fail closed" is a core security principle. If the security check
itself is unavailable, the safe default is to REFUSE, not to skip the check.
SENTINEL_FAIL_MODE=open exists only for local experiments.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.config import Settings
from orchestration.executor import AgentClient
from schemas.models import InvokeContext

log = logging.getLogger("conductor.guardrails")


class GuardrailBlocked(Exception):
    """The request was refused by Sentinel."""


class GuardrailUnavailable(Exception):
    """Sentinel could not be reached and we fail closed."""


@dataclass
class GuardResult:
    text: str
    notes: list[str] = field(default_factory=list)


class Guardrails:
    def __init__(self, client: AgentClient, settings: Settings):
        self.client, self.settings = client, settings

    async def _check(self, skill: str, text: str, ctx: InvokeContext,
                     kind: str = "answer") -> GuardResult:
        resp = await self.client.call("sentinel", skill, {"text": text, "kind": kind}, ctx)
        if resp.status != "ok":
            if self.settings.sentinel_fail_mode == "open":
                log.warning("sentinel_unavailable fail_mode=open skill=%s", skill)
                return GuardResult(text, ["WARNING: security check skipped (Sentinel unavailable)"])
            raise GuardrailUnavailable(resp.error or "sentinel error")
        out = resp.output
        notes = [str(n) for n in out.get("notes", [])]
        if not out.get("allowed", False):
            raise GuardrailBlocked("; ".join(notes) or "blocked by Sentinel")
        return GuardResult(str(out.get("text", "")), notes)

    async def check_input(self, text: str, ctx: InvokeContext) -> GuardResult:
        return await self._check("guard_input", text, ctx, kind="request")

    async def check_output(self, text: str, ctx: InvokeContext, kind: str = "answer") -> GuardResult:
        return await self._check("guard_output", text, ctx, kind)
