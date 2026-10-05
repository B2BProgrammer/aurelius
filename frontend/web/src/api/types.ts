/**
 * What the Conductor returns. These mirror the REAL agent outputs
 * (see agents/python/orchestrator/src/agents/recorded_responses.json).
 * Only the fields the screens use are typed; the rest is ignored.
 */

export interface Login {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: string;
}

export interface ClientSummary {
  client_id: string;
  household: string;
}

/** One agent's part of the overview: each section can fail on its own. */
export interface Section<T> {
  agent: string;
  skill: string;
  status: "ok" | "error";
  error: string | null;
  duration_ms: number;
  output: T;
}

export interface Overview {
  client_id: string;
  trace_id: string;
  generated_at: string;
  sections: {
    household: Section<Household>;
    portfolio: Section<Portfolio>;
    kyc: Section<Kyc>;
    risk: Section<Risk>;
    events: Section<EventsAnswer>;
    meetings: Section<Meetings>;
  };
}

// ---------------------------------------------------------------- Liaison
export interface Household {
  household: string;
  segment: string;
  members: Array<{ name: string; role: string; age: number }>;
  preferences: { contact_channel: "email" | "phone"; communication_style: string; salutation: string };
  last_contact: string;
  next_review: string;
  service_alerts: string[];
  open_tasks: Array<{ task_id: string; title: string; owner: "advisor" | "client"; due?: string; overdue: boolean }>;
  overdue_tasks: number;
}

// ---------------------------------------------------------------- Analyst
export type AssetClass = "equity" | "fixed_income" | "cash";
export interface Portfolio {
  total_value: number;
  as_of: string;
  allocation: {
    target_pct: Record<AssetClass, number>;
    current_pct: Record<AssetClass, number>;
    drift_pts: Record<AssetClass, number>;
    needs_rebalance: boolean;
  };
  concentration: Array<{ symbol: string; name: string; weight_pct: number; level: string; message: string }>;
  tax_loss_ideas: Array<{ symbol: string; name: string; unrealized_loss: number; replacements: string[]; note: string }>;
  actions: string[];
  summary: string;
}

// ---------------------------------------------------------------- Notary
export type Severity = "BLOCKER" | "ACTION" | "INFO";
export interface Kyc {
  status: "complete" | "action_needed" | "blocked";
  headline: string;
  counts: { blocker: number; action: number; info: number };
  issues: Array<{ rule: string; severity: Severity; member: string | null; message: string; fix: string }>;
}

// ---------------------------------------------------------------- Actuary
export interface Risk {
  risk_score: number;
  band: string;
  headline: string;
  willingness: number;
  capacity: { score: number };
  limiting_factor: "willingness" | "capacity";
  suggested_equity_pct: number;
  current_equity_pct: number;
  alignment: "aligned" | "portfolio_riskier_than_profile" | "portfolio_more_conservative_than_profile";
  notes: string[];
  portfolio_source: string;
}

export interface RetirementScenario {
  retire_age: number;
  annual_spending: number;
  probability_of_success_pct: number;
  median_at_retirement: number;
  worst_case_age_money_lasts: number;
  balance_at_plan_end: { p10: number; p50: number; p90: number };
  median_path_by_age: Record<string, number>;
}

export interface Retirement {
  headline: string;
  already_retired: boolean;
  ages_are_of: string;
  scenarios: RetirementScenario[];
  comparison: string[];
  inputs: { annual_spending: number; annual_savings_until_retirement: number; plan_to_age: number };
  disclosure: string;
  portfolio_source: string;
}

export interface StressTest {
  headline: string;
  scenarios: Array<{ scenario: string; name: string; loss: number; loss_pct: number; years_of_spending: number | null; note: string }>;
  disclosure: string;
}

// ---------------------------------------------------------------- Pulse
export interface MarketEvent {
  event_id: string;
  date: string;
  severity: "low" | "medium" | "high";
  headline: string;
  summary?: string;
  match?: "direct" | "indirect";
  holdings_hit?: string[];
  exposure_pct?: number;
  estimated_impact?: number;
  why?: string;
}

export interface EventsAnswer {
  headline: string;
  count: number;
  events: MarketEvent[];
  holdings_source: string;
}

// ---------------------------------------------------------------- Scribe
export interface Meetings {
  meetings_found: number;
  last_meeting: string | null;
  summary: string;
  open_action_items: Array<{ owner: string; task: string; due: string | null }>;
  client_concerns: string[];
  life_events: string[];
  compliance_flags: Array<{ type: string; detail: string }>;
}

// ---------------------------------------------------------------- Herald
export interface EmailDraft {
  subject: string;
  body: string;
  to: string[];
  tone: string;
  compliance: { fixes: string[]; disclosure_added: boolean; warnings: string[] };
  warnings: string[];
  drafted_by: string;
}

export interface Approval {
  approved: boolean;
  note_id?: string;
  next_step?: string;
  reason?: string;
  revised_body?: string;
  guardrail_notes: string[];
}

// ---------------------------------------------------------------- skills + chat
export interface SkillResult<T> {
  agent: string;
  skill: string;
  status: "ok" | "error";
  error: string | null;
  trace_id: string;
  duration_ms: number;
  output: T;
  guardrail_notes: string[];
}

export interface ChatStep {
  agent: string;
  skill: string;
  status: "ok" | "error";
  duration_ms: number;
  error: string | null;
}

export interface ChatAnswer {
  trace_id: string;
  answer: string;
  steps: ChatStep[];
  plan: { source: "llm" | "rules"; stages: Array<Array<{ agent: string; skill: string; reason: string }>> };
  drafts: Array<{ kind: string; content: Partial<EmailDraft> & { subject?: string; body?: string } }>;
  guardrail_notes: string[];
}
