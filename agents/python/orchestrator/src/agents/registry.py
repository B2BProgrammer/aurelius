"""
Agent registry: which agents exist, where they live, and what they can do.

LEARN: The planner LLM reads these descriptions to decide who to call, so
clear skill descriptions = better plans. In production you'd build this from
each agent's /.well-known/agent.json card instead of hard-coding it.

UI_SKILLS is a separate, explicit ALLOWLIST: the skills the web and mobile apps
may call directly (POST /v1/skills/{agent}/{skill}). Read-only skills only:
anything that writes (CRM notes, KYC documents, AML screening) goes through a
dedicated, audited endpoint or through the chat pipeline, never this door.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.config import Settings


@dataclass(frozen=True)
class AgentInfo:
    name: str
    codename: str
    language: str
    url: str
    description: str
    skills: dict[str, str] = field(default_factory=dict)  # skill -> what it does
    plannable: bool = True  # Sentinel is called by the pipeline, never by the planner


def build_registry(s: Settings) -> dict[str, AgentInfo]:
    agents = [
        AgentInfo("sentinel", "Sentinel", "Python", s.sentinel_url,
                  "Security guardrails for every request and answer.",
                  {"guard_input": "Mask PII and block prompt injection in the advisor's request.",
                   "guard_output": "Check an answer for PII leaks and add required disclosures."},
                  plannable=False),
        AgentInfo("librarian", "Librarian", "Python", s.librarian_url,
                  "Searches firm research, product docs and policies (RAG).",
                  {"search_knowledge": "Answer a question from firm documents, with citations. "
                                       "input: {query}"}),
        AgentInfo("analyst", "Analyst", "Python", s.analyst_url,
                  "Portfolio analytics for a client household.",
                  {"analyze_portfolio": "Allocation drift, concentration risk and tax-loss ideas. "
                                        "input: {client_id}"}),
        AgentInfo("scribe", "Scribe", "Python", s.scribe_url,
                  "Meeting notes intelligence.",
                  {"summarize_meetings": "Summarize recent meeting notes and open action items. "
                                         "input: {client_id}"}),
        AgentInfo("herald", "Herald", "TypeScript", s.herald_url,
                  "Client communications (drafts only; a human approves and sends).",
                  {"draft_email": "Draft a client email in the household's style. "
                                  "input: {client_id, purpose, points?}",
                   "review_email": "Compliance-check an email the advisor wrote. input: {text, client_id?}"}),
        AgentInfo("liaison", "Liaison", "TypeScript", s.liaison_url,
                  "CRM read/write.",
                  {"get_household": "Household profile, preferences, open tasks. input: {client_id}",
                   "list_tasks": "Open and done tasks with overdue flags. input: {client_id}",
                   "log_note": "Save a note to the CRM. input: {client_id, note, type?}"}),
        AgentInfo("notary", "Notary", "Java", s.notary_url,
                  "Onboarding and KYC/AML.",
                  {"check_kyc": "KYC/AML status: blockers, action items, fixes. input: {client_id}",
                   "list_documents": "Documents on file (numbers masked). input: {client_id}"}),
        AgentInfo("actuary", "Actuary", "Java", s.actuary_url,
                  "Risk and retirement math.",
                  {"project_retirement": "Monte Carlo retirement projection; can compare retirement "
                                         "ages. input: {client_id, retire_ages?, annual_spending?}",
                   "risk_score": "Client risk score and portfolio alignment. input: {client_id}",
                   "stress_test": "Losses if past crises repeated. input: {client_id}"}),
        AgentInfo("pulse", "Pulse", "Go", s.pulse_url,
                  "Market and news events.",
                  {"get_events": "Recent market/news events affecting a client's holdings. "
                                 "input: {client_id}",
                   "scan_clients": "Which households recent events affect most. input: {}"}),
    ]
    return {a.name: a for a in agents}


# What the apps may call directly. Read-only, explicit, reviewed.
UI_SKILLS: dict[str, set[str]] = {
    "librarian": {"search_knowledge"},
    "analyst": {"analyze_portfolio"},
    "scribe": {"summarize_meetings"},
    "herald": {"draft_email", "review_email"},   # drafting never sends anything
    "liaison": {"get_household", "list_tasks"},
    "notary": {"check_kyc", "list_documents"},
    "actuary": {"risk_score", "project_retirement", "stress_test"},
    "pulse": {"get_events", "scan_clients", "list_events"},
}


def describe_for_planner(registry: dict[str, AgentInfo]) -> str:
    lines = []
    for a in registry.values():
        if not a.plannable:
            continue
        lines.append(f"- {a.name}: {a.description}")
        for skill, desc in a.skills.items():
            lines.append(f"    * {skill}: {desc}")
    return "\n".join(lines)
