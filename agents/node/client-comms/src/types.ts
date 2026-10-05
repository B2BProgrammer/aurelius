/**
 * Types for what the Herald receives from the Liaison and what it returns.
 */

/** The part of the Liaison's get_household output the Herald uses. */
export interface HouseholdInfo {
  client_id: string;
  household: string;
  members: Array<{ name: string; role: string; age: number; email: string | null; phone: string | null }>;
  preferences: { contact_channel: "email" | "phone"; communication_style: string; salutation: string };
  next_review: string;
  service_alerts: string[];
  open_tasks: Array<{ task_id: string; title: string; owner: "advisor" | "client"; due?: string; overdue: boolean }>;
}

export type Intent = "meeting_follow_up" | "meeting_prep" | "thank_you" | "scheduling" | "check_in";

export interface ComplianceReport {
  /** Rules that changed the text, e.g. CMP_GUARANTEE, PII_SSN. */
  fixes: string[];
  disclosure_added: boolean;
  /** Things the advisor must look at but code can't fix. */
  warnings: string[];
}

export interface DraftResult {
  subject: string;
  body: string;
  to: string[];
  salutation: string;
  intent: Intent;
  tone: "warm" | "formal" | "brief";
  channel_preference: "email" | "phone" | "unknown";
  personalized: boolean;
  compliance: ComplianceReport;
  warnings: string[];
  requires_approval: true;
  drafted_by: string;
}
