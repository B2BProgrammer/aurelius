import { ApiError } from "../api/client";

/** Says what went wrong in plain words, with the trace ID so it can be found in the logs. */
export function ErrorNote({ error, what }: { error: unknown; what: string }) {
  const traceId = error instanceof ApiError ? error.traceId : null;
  let message = error instanceof Error ? error.message : String(error);
  if (error instanceof ApiError && error.status === 0) message = "The Conductor isn't reachable.";
  if (error instanceof TypeError) message = "The Conductor isn't reachable. Check it's running on port 8000.";
  return (
    <div className="note error" role="alert">
      Couldn't load {what}. {message}
      {traceId && <span className="trace">Trace {traceId}</span>}
    </div>
  );
}

export function Skeleton() {
  return (
    <div aria-hidden="true">
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}
