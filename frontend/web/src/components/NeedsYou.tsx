import type { Overview } from "../api/types";
import { day, signedMoney } from "../lib/format";

export interface Need {
  kind: string;
  blocker?: boolean;
  text: string;
  detail?: string;
}

/**
 * Pulls the things an advisor must act on out of six agents' answers,
 * most urgent first. Pure function, so it's easy to test.
 */
export function collectNeeds(o: Overview): Need[] {
  const s = o.sections;
  const needs: Need[] = [];

  if (s.kyc.status === "ok") {
    for (const i of s.kyc.output.issues) {
      if (i.severity === "BLOCKER") needs.push({ kind: "Blocker", blocker: true, text: i.message, detail: i.fix });
    }
    for (const i of s.kyc.output.issues) {
      if (i.severity === "ACTION") needs.push({ kind: "Paperwork", text: i.message, detail: i.fix });
    }
  }
  if (s.household.status === "ok") {
    for (const t of s.household.output.open_tasks) {
      if (t.overdue && t.owner === "advisor")
        needs.push({ kind: "Overdue", text: t.title, detail: t.due ? `Was due ${day(t.due)}` : undefined });
    }
  }
  if (s.events.status === "ok") {
    for (const e of s.events.output.events) {
      if (e.severity === "high" && e.match === "direct")
        needs.push({
          kind: "Market",
          text: e.headline,
          detail: e.estimated_impact !== undefined ? `About ${signedMoney(e.estimated_impact)} for this household` : e.why,
        });
    }
  }
  if (s.portfolio.status === "ok") {
    const p = s.portfolio.output;
    if (p.allocation.needs_rebalance) {
      const eq = p.allocation.drift_pts.equity;
      needs.push({
        kind: "Rebalance",
        text: `Stocks are ${Math.abs(eq)} points ${eq > 0 ? "over" : "under"} target.`,
        detail: p.actions[0],
      });
    }
    for (const c of p.concentration) needs.push({ kind: "Concentration", text: c.message });
  }
  if (s.risk.status === "ok" && s.risk.output.alignment !== "aligned") {
    needs.push({ kind: "Risk", text: s.risk.output.headline });
  }
  return needs;
}

export function NeedsYou({ overview }: { overview: Overview }) {
  const needs = collectNeeds(overview);
  if (needs.length === 0) return <p className="all-clear">Nothing needs you today. The file is in order.</p>;
  return (
    <ul className="needs">
      {needs.map((n, i) => (
        <li key={i}>
          <span className={`kind ${n.blocker ? "blocker" : ""}`}>{n.kind}</span>
          <div>
            {n.text}
            {n.detail && <div className="detail">{n.detail}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}
