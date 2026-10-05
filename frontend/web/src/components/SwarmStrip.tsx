import type { Overview } from "../api/types";

export const AGENT_NAME: Record<string, string> = {
  liaison: "Liaison",
  analyst: "Analyst",
  notary: "Notary",
  actuary: "Actuary",
  pulse: "Pulse",
  scribe: "Scribe",
  herald: "Herald",
  librarian: "Librarian",
  sentinel: "Sentinel",
};

/**
 * Which agents answered for this file, and how long each took.
 * The one motion moment on the page: the ticks arrive one after another.
 */
export function SwarmStrip({ overview }: { overview: Overview }) {
  const sections = Object.values(overview.sections);
  return (
    <div className="swarm" aria-label="Agents that prepared this file">
      {sections.map((s, i) => (
        <span
          key={s.agent + s.skill}
          className={`swarm-item ${s.status === "error" ? "error" : ""}`}
          style={{ animationDelay: `${i * 70}ms` }}
          title={s.error ?? `${s.skill} answered in ${s.duration_ms} ms`}
        >
          <span className="tick" aria-hidden="true" />
          {AGENT_NAME[s.agent] ?? s.agent}
          <span className="ms">{s.status === "error" ? "didn't answer" : `${s.duration_ms} ms`}</span>
        </span>
      ))}
    </div>
  );
}
