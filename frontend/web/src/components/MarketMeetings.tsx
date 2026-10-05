import type { EventsAnswer, Meetings } from "../api/types";
import { day, shortDay, signedMoney } from "../lib/format";

export function MarketBody({ ev }: { ev: EventsAnswer }) {
  if (ev.count === 0) return <p className="prose">No market news in the last two weeks touches this portfolio.</p>;
  return (
    <ul className="events">
      {ev.events.map((e) => (
        <li key={e.event_id}>
          <span className="when">{shortDay(e.date)}</span>
          <div>
            <div className="head">
              <span className={`dot ${e.severity}`} aria-label={`${e.severity} severity`} role="img" />
              <span>{e.headline}</span>
            </div>
            {e.why && <div className="why">{e.why}</div>}
          </div>
          <span className={`impact ${(e.estimated_impact ?? 0) < 0 ? "neg" : "pos"}`}>
            {e.estimated_impact !== undefined && e.estimated_impact !== 0 ? signedMoney(e.estimated_impact) : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function MeetingsBody({ m }: { m: Meetings }) {
  if (m.meetings_found === 0) return <p className="prose">No meeting notes on file yet.</p>;
  return (
    <>
      <p className="lede">{m.summary}</p>
      {m.last_meeting && <p className="hint">Last meeting {day(m.last_meeting)}</p>}
      <div className="two-col">
        <div>
          <h3>Promised in the meeting</h3>
          <ul className="plain-list">
            {m.open_action_items.map((a, i) => (
              <li key={i}>
                {a.task}
                <span className="hint">
                  {" "}
                  ({a.owner === "advisor" ? "you" : a.owner}
                  {a.due ? `, by ${shortDay(a.due)}` : ""})
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          {m.client_concerns.length > 0 && (
            <>
              <h3>What's on their mind</h3>
              <ul className="plain-list">
                {m.client_concerns.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </>
          )}
          {m.life_events.length > 0 && (
            <>
              <h3 style={{ marginTop: "1rem" }}>Life events</h3>
              <ul className="plain-list">
                {m.life_events.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
      {m.compliance_flags.length > 0 && (
        <div className="note warn">
          Compliance: {m.compliance_flags.map((f) => f.detail).join(" ")}
        </div>
      )}
    </>
  );
}
