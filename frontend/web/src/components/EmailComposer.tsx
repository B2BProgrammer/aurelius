import { useState, type FormEvent } from "react";

import { useApproveDraft, useDraftEmail } from "../api/hooks";
import type { Approval } from "../api/types";
import { ErrorNote } from "./ErrorNote";

const PURPOSES = [
  "Follow up on our last meeting",
  "Prepare for our upcoming review",
  "Check in about recent market news",
];

/**
 * Human in the loop: Herald drafts, the advisor edits, Sentinel checks it again,
 * and only an explicit approval writes a note to the CRM. Atrium never sends email.
 */
export function EmailComposer({ clientId }: { clientId: string }) {
  const [purpose, setPurpose] = useState(PURPOSES[0] ?? "");
  const [points, setPoints] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [approval, setApproval] = useState<Approval | null>(null);
  const draft = useDraftEmail();
  const approve = useApproveDraft();

  async function onDraft(e: FormEvent) {
    e.preventDefault();
    setApproval(null);
    const res = await draft.mutateAsync({
      clientId,
      purpose,
      points: points.split("\n").map((p) => p.trim()).filter(Boolean),
    });
    if (res.status === "ok") {
      setSubject(res.output.subject);
      setBody(res.output.body);
    }
  }

  async function onApprove() {
    const res = await approve.mutateAsync({ clientId, subject, body });
    setApproval(res);
    if (!res.approved && res.revised_body) setBody(res.revised_body);
  }

  function startOver() {
    draft.reset();
    approve.reset();
    setApproval(null);
    setSubject("");
    setBody("");
  }

  const out = draft.data?.status === "ok" ? draft.data.output : null;
  const hasPlaceholder = /\[[^\]]+\]/.test(body);
  // Herald's warnings describe its first draft; drop the placeholder one once the advisor has filled them in.
  const warnings = out
    ? [...out.compliance.warnings, ...out.warnings].filter((w) => hasPlaceholder || !/placeholder/i.test(w))
    : [];

  if (!out) {
    return (
      <form className="composer" onSubmit={onDraft}>
        <div className="field">
          <label htmlFor="purpose">What's the email for?</label>
          <input id="purpose" list="purposes" value={purpose} onChange={(e) => setPurpose(e.target.value)} required />
          <datalist id="purposes">
            {PURPOSES.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </div>
        <div className="field">
          <label htmlFor="points">Points to include, one per line</label>
          <textarea id="points" rows={3} value={points} onChange={(e) => setPoints(e.target.value)} />
          <span className="hint">Herald adds open tasks and the review date from the CRM.</span>
        </div>
        {draft.isError && <ErrorNote error={draft.error} what="a draft" />}
        {draft.data?.status === "error" && <div className="note error">Herald couldn't draft it: {draft.data.error}</div>}
        <div className="row">
          <button className="btn" type="submit" disabled={draft.isPending}>
            {draft.isPending ? "Drafting…" : "Draft email"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="composer">
      {out.compliance.fixes.length > 0 && (
        <div className="note warn">
          Herald's compliance check changed the draft ({out.compliance.fixes.join(", ")}). Read it before approving.
        </div>
      )}
      {warnings.map((w, i) => (
        <div className="note warn" key={i}>
          {w}
        </div>
      ))}

      <div className="letter">
        <div className="to">To {out.to.join(", ")}</div>
        <label htmlFor="subject" className="visually-hidden">
          Subject
        </label>
        <input
          id="subject"
          className="subject"
          value={subject}
          onChange={(e) => {
            setSubject(e.target.value);
            setApproval(null);
          }}
        />
        <label htmlFor="body" className="visually-hidden">
          Email body
        </label>
        <textarea
          id="body"
          value={body}
          onChange={(e) => {
            setBody(e.target.value);
            setApproval(null);
          }}
        />
      </div>

      {approve.isError && <ErrorNote error={approve.error} what="the approval" />}
      {approval?.approved && (
        <div className="note ok" role="status">
          Approved and logged to the CRM as note {approval.note_id}. {approval.next_step}
        </div>
      )}
      {approval && !approval.approved && (
        <div className="note error" role="alert">
          {approval.reason} {approval.guardrail_notes.join(" ")}
        </div>
      )}

      <div className="row">
        <button
          className="btn"
          type="button"
          onClick={onApprove}
          disabled={approve.isPending || approval?.approved === true || hasPlaceholder}
        >
          {approve.isPending ? "Checking…" : approval?.approved ? "Approved" : "Approve and log to CRM"}
        </button>
        <button className="btn quiet" type="button" onClick={startOver}>
          Start over
        </button>
        {hasPlaceholder && <span className="hint">Fill in the [bracketed] placeholders first.</span>}
      </div>
    </div>
  );
}
