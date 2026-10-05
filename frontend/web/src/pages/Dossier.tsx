import { useParams } from "react-router";

import { ApiError } from "../api/client";
import { useOverview } from "../api/hooks";
import { AskPanel } from "../components/AskPanel";
import { EmailComposer } from "../components/EmailComposer";
import { ErrorNote, Skeleton } from "../components/ErrorNote";
import { MarketBody, MeetingsBody } from "../components/MarketMeetings";
import { Memo, SectionBody } from "../components/Memo";
import { NeedsYou } from "../components/NeedsYou";
import { PortfolioBody } from "../components/PortfolioSection";
import { RetirementSection } from "../components/RetirementSection";
import { SwarmStrip } from "../components/SwarmStrip";
import { day, moneyShort } from "../lib/format";

/** One household's file, read top to bottom like a memo. */
export function Dossier() {
  const { clientId = "" } = useParams();
  const q = useOverview(clientId);

  if (q.isPending)
    return (
      <div aria-busy="true">
        <p className="hint">Asking six agents for this file…</p>
        <Skeleton />
      </div>
    );
  if (q.isError) {
    if (q.error instanceof ApiError && q.error.status === 404)
      return <div className="note error">There's no household with the id {clientId}.</div>;
    return <ErrorNote error={q.error} what="this household" />;
  }

  const o = q.data;
  const s = o.sections;
  const h = s.household.status === "ok" ? s.household.output : null;
  const value = s.portfolio.status === "ok" ? s.portfolio.output.total_value : null;

  return (
    <article key={clientId}>
      <header className="dossier-head">
        <div>
          <h1>{h?.household ?? clientId}</h1>
          {h && (
            <p className="members">
              {h.members.map((m) => `${m.name}, ${m.age}`).join(" and ")}. {h.segment}.
              {h.next_review && <> Next review {day(h.next_review)}.</>}
            </p>
          )}
        </div>
        {value !== null && (
          <div className="dossier-figure">
            <div className="value">{moneyShort(value)}</div>
            <div className="label">under management</div>
          </div>
        )}
      </header>

      <SwarmStrip overview={o} />

      <Memo title="Needs you" id="needs">
        <NeedsYou overview={o} />
      </Memo>

      <Memo title="Portfolio" by="Analyst and Actuary" id="portfolio">
        <SectionBody section={s.portfolio}>{(p) => <PortfolioBody p={p} risk={s.risk} />}</SectionBody>
      </Memo>

      <Memo title="Retirement" by="Actuary" id="retirement">
        <RetirementSection key={clientId} clientId={clientId} />
      </Memo>

      <Memo title="Market" by="Pulse" id="market">
        <SectionBody section={s.events}>{(ev) => <MarketBody ev={ev} />}</SectionBody>
      </Memo>

      <Memo title="Meetings" by="Scribe" id="meetings">
        <SectionBody section={s.meetings}>{(m) => <MeetingsBody m={m} />}</SectionBody>
      </Memo>

      <Memo title="Write to them" by="Herald, checked by Sentinel" id="email">
        <EmailComposer key={clientId} clientId={clientId} />
      </Memo>

      <Memo title="Ask Aurelius" by="the Conductor" id="ask">
        <AskPanel key={clientId} clientId={clientId} />
      </Memo>

      <p className="fine" style={{ marginTop: "1.5rem" }}>
        Prepared {new Date(o.generated_at).toLocaleString()}. Trace {o.trace_id}. All households are fictional.
      </p>
    </article>
  );
}
