import { useState, type FormEvent } from "react";
import Markdown from "react-markdown";

import { useAsk } from "../api/hooks";
import { ErrorNote } from "./ErrorNote";
import { AGENT_NAME } from "./SwarmStrip";

const SUGGESTIONS = [
  "What does our policy say about single-stock concentration?",
  "Prepare me for the next review",
  "How exposed is this household to this week's news?",
];

/**
 * Free-form questions go to /v1/chat: the Conductor plans which agents to ask,
 * runs them in parallel and writes one answer.
 * react-markdown renders text only (no raw HTML), so an answer can't inject script.
 */
export function AskPanel({ clientId }: { clientId: string | null }) {
  const [message, setMessage] = useState("");
  const ask = useAsk();

  function submit(text: string) {
    const m = text.trim();
    if (!m) return;
    setMessage(m);
    ask.mutate({ message: m, clientId });
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(message);
  }

  return (
    <div className="ask">
      <form onSubmit={onSubmit} role="search">
        <label htmlFor="ask-input" className="visually-hidden">
          Ask Aurelius
        </label>
        <input
          id="ask-input"
          placeholder="Ask about this household, the firm's policies or the markets"
          value={message}
          maxLength={2000}
          onChange={(e) => setMessage(e.target.value)}
        />
        <button className="btn" type="submit" disabled={ask.isPending}>
          {ask.isPending ? "Asking…" : "Ask"}
        </button>
      </form>

      {!ask.data && !ask.isPending && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="linkish" onClick={() => submit(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      {ask.isError && <ErrorNote error={ask.error} what="an answer" />}
      {ask.data && (
        <div aria-live="polite">
          <div className="answer">
            <Markdown>{ask.data.answer}</Markdown>
          </div>
          <p className="hint" style={{ marginTop: "0.8rem" }}>
            Answered by{" "}
            {ask.data.steps
              .map((s) => `${AGENT_NAME[s.agent] ?? s.agent} (${s.status === "ok" ? `${s.duration_ms} ms` : "failed"})`)
              .join(", ")}
            . Planned by {ask.data.plan.source === "llm" ? "the language model" : "the fallback rules"}.
          </p>
          {ask.data.guardrail_notes.length > 0 && (
            <div className="note warn" style={{ marginTop: "0.6rem" }}>
              {ask.data.guardrail_notes.join(" ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
