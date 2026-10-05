"""
Pipeline: the 7 phases from the sequence diagram, in order.

  1. receive request        (main.py)
  2. input guard            Sentinel.guard_input
  3+4. plan and execute     Planner + Executor (parallel stages)
  5. drafts                 Herald's email becomes a Draft that needs approval
  6. output guard           Sentinel.guard_output (answer and each draft)
  7. return to Atrium       the advisor reviews and approves
"""
from __future__ import annotations

import logging
import uuid

from orchestration.executor import AgentClient, run_plan
from security.guardrails import Guardrails
from schemas.models import ChatRequest, ChatResponse, Draft, InvokeContext
from orchestration.planner import Planner
from orchestration.synthesizer import Synthesizer

log = logging.getLogger("conductor.pipeline")


class Pipeline:
    def __init__(self, planner: Planner, client: AgentClient, guardrails: Guardrails,
                 synthesizer: Synthesizer):
        self.planner, self.client = planner, client
        self.guardrails, self.synthesizer = guardrails, synthesizer

    async def handle(self, req: ChatRequest, user_id: str, trace_id: str | None = None) -> ChatResponse:
        ctx = InvokeContext(trace_id=trace_id or uuid.uuid4().hex, user_id=user_id,
                            client_id=req.client_id)
        # LEARN: audit log has who/when/what-kind, never the message text (it may hold PII)
        log.info("request_start trace=%s user=%s client=%s chars=%d",
                 ctx.trace_id, user_id, req.client_id, len(req.message))

        # Phase 2: input guard (raises GuardrailBlocked / GuardrailUnavailable)
        guarded_in = await self.guardrails.check_input(req.message, ctx)
        notes = list(guarded_in.notes)
        safe_message = guarded_in.text  # PII is masked from here on, the LLM never sees it

        # Phases 3 and 4: plan, then run stages (parallel inside each stage)
        plan = await self.planner.plan(safe_message, req.client_id)
        results = await run_plan(plan, self.client, ctx)

        # Phase 5: drafts that need human approval
        drafts: list[Draft] = []
        for r in results:
            if r.agent == "herald" and r.status == "ok":
                body_check = await self.guardrails.check_output(
                    str(r.output.get("body", "")), ctx, kind="email")
                content = {**r.output, "body": body_check.text}
                drafts.append(Draft(kind="email", content=content))
                notes.extend(f"Email draft: {n}" for n in body_check.notes)

        # Phase 6: write and check the answer
        answer = await self.synthesizer.synthesize(safe_message, results)
        guarded_out = await self.guardrails.check_output(answer, ctx)
        notes.extend(guarded_out.notes)

        log.info("request_done trace=%s steps=%d failed=%d drafts=%d plan_source=%s",
                 ctx.trace_id, len(results), sum(r.status != "ok" for r in results),
                 len(drafts), plan.source)
        # Phase 7: back to Atrium
        return ChatResponse(trace_id=ctx.trace_id, answer=guarded_out.text, plan=plan,
                            steps=results, drafts=drafts, guardrail_notes=notes)
