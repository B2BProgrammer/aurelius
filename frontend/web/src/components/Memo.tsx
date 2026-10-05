import type { ReactNode } from "react";

import type { Section } from "../api/types";
import { AGENT_NAME } from "./SwarmStrip";

/** One section of the dossier: its name in the margin, the content beside it. */
export function Memo({ title, by, id, children }: { title: string; by?: string; id?: string; children: ReactNode }) {
  const headingId = id ? `${id}-h` : undefined;
  return (
    <section className="memo-section" id={id} aria-labelledby={headingId}>
      <div className="memo-margin">
        <h2 id={headingId}>{title}</h2>
        {by && <p className="by">from {by}</p>}
      </div>
      <div className="memo-body">{children}</div>
    </section>
  );
}

/** Shows a section's content, or says plainly which agent didn't answer. */
export function SectionBody<T>({ section, children }: { section: Section<T>; children: (out: T) => ReactNode }) {
  if (section.status !== "ok") {
    return (
      <div className="note error" role="status">
        {AGENT_NAME[section.agent] ?? section.agent} didn't answer: {section.error ?? "unknown error"}. The rest of the
        file is still current.
      </div>
    );
  }
  return <>{children(section.output)}</>;
}
