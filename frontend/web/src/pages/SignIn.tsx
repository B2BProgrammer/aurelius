import { useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../lib/auth";

export function SignIn() {
  const { signIn, notice } = useAuth();
  const [username, setUsername] = useState("advisor");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(username.trim(), password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setError("Too many attempts. Wait five minutes, then try again.");
      else if (err instanceof ApiError && err.status === 401) setError("That username and password don't match.");
      else if (err instanceof ApiError && err.status === 404)
        setError("Sign-in is turned off. Set DEV_LOGIN_PASSWORD in aurelius\\.env and restart the Conductor.");
      else setError("The Conductor isn't reachable. Check it's running on port 8000.");
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <main className="signin">
      <section className="signin-mark">
        <div>
          <h1>Atrium</h1>
          <p>
            Every household you look after, prepared by the Aurelius agents before you open the file:
            portfolio, paperwork, plans and the news that touches them.
          </p>
        </div>
        <p className="signin-roster">
          Librarian, Analyst, Scribe, Sentinel, Herald, Liaison, Notary, Actuary and Pulse work behind
          this screen. Nothing reaches a client until you approve it.
        </p>
      </section>

      <form className="signin-form" onSubmit={onSubmit} aria-describedby={error ? "signin-error" : undefined}>
        <h2>Sign in</h2>
        {notice && <div className="note warn">{notice}</div>}
        <div className="field">
          <label htmlFor="username">Username</label>
          <input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <span className="hint">The DEV_LOGIN_PASSWORD from your .env file.</span>
        </div>
        {error && (
          <div id="signin-error" className="note error" role="alert">
            {error}
          </div>
        )}
        <div>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </main>
  );
}
