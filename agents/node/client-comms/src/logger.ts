/**
 * One JSON object per line, same format as the Python agents, so one log
 * search ("trace=abc123") follows a request across every agent.
 * Rule: log ids, counts and timings. Never note text or contact details.
 */
type Level = "INFO" | "WARNING" | "ERROR";

export interface Logger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

function write(level: Level, logger: string, msg: string): void {
  const line = JSON.stringify({ ts: new Date().toISOString(), level, logger, msg });
  if (level === "ERROR") console.error(line);
  else console.log(line);
}

export function getLogger(name: string): Logger {
  return {
    info: (msg) => write("INFO", name, msg),
    warn: (msg) => write("WARNING", name, msg),
    error: (msg) => write("ERROR", name, msg),
  };
}
