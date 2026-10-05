import { useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router";

import { useClients } from "../api/hooks";
import { openStream } from "../api/stream";
import type { MarketEvent } from "../api/types";
import { ErrorNote, Skeleton } from "../components/ErrorNote";
import { useAuth } from "../lib/auth";
import { shortDay } from "../lib/format";

type StreamStatus = "connecting" | "live" | "offline";

/** The frame around every screen: households on the left, live news under them. */
export function Workspace() {
  const { session, signOut } = useAuth();
  const clients = useClients();
  const { clientId } = useParams();
  const [news, setNews] = useState<MarketEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("connecting");

  const token = session?.token ?? null;
  useEffect(() => {
    if (!token) return;
    return openStream(token, null, {
      onStatus: setStatus,
      onEvent: (e) => setNews((prev) => [e, ...prev.filter((p) => p.event_id !== e.event_id)].slice(0, 8)),
    });
  }, [token]);

  return (
    <div className="workspace">
      <nav className="rail" aria-label="Households">
        <div className="rail-brand">
          <strong>Atrium</strong>
        </div>

        <div>
          <h2>Your households</h2>
          {clients.isPending && <Skeleton />}
          {clients.isError && <ErrorNote error={clients.error} what="your households" />}
          {clients.data && (
            <ul>
              {clients.data.map((c) => (
                <li key={c.client_id}>
                  <NavLink
                    className="household-link"
                    to={`/clients/${c.client_id}`}
                    aria-current={c.client_id === clientId ? "page" : undefined}
                  >
                    <span className="name">{c.household.replace(/ household$/i, "")}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </div>

        <section className="news" aria-label="Live market news" aria-live="polite">
          <h2>Market news</h2>
          <div className="news-status">
            <span className={`dot ${status === "live" ? "live" : ""}`} />
            {status === "live" ? "Listening to Pulse" : status === "connecting" ? "Connecting…" : "Offline, retrying"}
          </div>
          {news.length === 0 && status === "live" && (
            <p className="hint">Nothing new yet. Events appear here the moment Pulse sees them.</p>
          )}
          {news.map((e) => (
            <article className="news-item" key={e.event_id}>
              <div className="when">
                {shortDay(e.date)}{e.severity === "high" ? ", high severity" : ""}
              </div>
              {e.headline}
            </article>
          ))}
        </section>

        <div className="rail-foot">
          <span>{session?.user}</span>
          <button className="linkish" type="button" onClick={() => signOut()}>
            Sign out
          </button>
        </div>
      </nav>

      <main className="main" id="main">
        <Outlet />
      </main>
    </div>
  );
}

export function Welcome() {
  const { session } = useAuth();
  return (
    <div className="empty-main">
      <h1>Good to see you, {session?.user}.</h1>
      <p>
        Pick a household on the left. Atrium asks six agents for their part of the file at once, and shows you
        what needs your attention first.
      </p>
    </div>
  );
}
