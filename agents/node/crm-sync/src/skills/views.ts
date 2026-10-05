/**
 * What OTHER agents get to see of a household.
 *
 * LEARN: "Minimum necessary". The CRM stores full emails and phone numbers,
 * but no other agent needs them: the Herald drafts emails that the ADVISOR
 * sends from their own mailbox. So agents get "r***@example.com".
 */
import type { Household, HouseholdView, Task, TaskView } from "../types.js";

export function maskEmail(email: string | undefined): string | null {
  if (!email) return null;
  const [user = "", domain = ""] = email.split("@");
  return `${user.slice(0, 1)}***@${domain}`;
}

export function maskPhone(phone: string | undefined): string | null {
  return phone ? `***-***-${phone.slice(-4)}` : null;
}

export function taskView(task: Task, today: string): TaskView {
  return { ...task, overdue: task.status === "open" && task.due !== undefined && task.due < today };
}

export function householdView(clientId: string, h: Household, today: string): HouseholdView {
  const open = h.tasks.filter((t) => t.status === "open").map((t) => taskView(t, today));
  return {
    client_id: clientId,
    household: h.household,
    segment: h.segment,
    members: h.members.map((m) => ({
      name: m.name, role: m.role, age: m.age,
      email: maskEmail(m.email), phone: maskPhone(m.phone),
    })),
    preferences: h.preferences,
    accounts: h.accounts,
    last_contact: h.last_contact,
    next_review: h.next_review,
    service_alerts: h.service_alerts,
    open_tasks: open,
    overdue_tasks: open.filter((t) => t.overdue).length,
    recent_notes: [...h.notes].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 3),
  };
}
