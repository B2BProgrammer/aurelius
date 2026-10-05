/**
 * Reads the Conductor's live event stream (Server-Sent Events) with fetch().
 *
 * LEARN: the browser's built-in EventSource can't send an Authorization header,
 * and tokens must never go in URLs (they end up in logs). So we read the
 * response body ourselves: split on blank lines, parse "event:" and "data:".
 * When the stream ends (the server closes it every 30 minutes) we reconnect.
 */
import type { MarketEvent } from "./types";

export interface StreamHandlers {
  onEvent: (e: MarketEvent) => void;
  onStatus: (s: "connecting" | "live" | "offline") => void;
}

export function parseSSE(chunk: string): Array<{ event: string; data: string }> {
  const out: Array<{ event: string; data: string }> = [];
  for (const block of chunk.split(/\r?\n\r?\n/)) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (data.length) out.push({ event, data: data.join("\n") });
  }
  return out;
}

/** Starts streaming; returns a function that stops it. */
export function openStream(token: string, clientId: string | null, h: StreamHandlers): () => void {
  const controller = new AbortController();
  let stopped = false;

  const run = async (): Promise<void> => {
    let delay = 1000;
    while (!stopped) {
      h.onStatus("connecting");
      try {
        const url = clientId ? `/v1/stream?client_id=${encodeURIComponent(clientId)}` : "/v1/stream";
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
        h.onStatus("live");
        delay = 1000;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const cut = buffer.lastIndexOf("\n\n");
          if (cut < 0) continue;
          for (const msg of parseSSE(buffer.slice(0, cut))) {
            if (msg.event === "market_event") h.onEvent(JSON.parse(msg.data) as MarketEvent);
          }
          buffer = buffer.slice(cut + 2);
        }
      } catch {
        if (stopped) return;
        h.onStatus("offline");
      }
      await new Promise((r) => setTimeout(r, delay));
      delay = Math.min(delay * 2, 30_000); // back off: don't hammer a server that's down
    }
  };
  void run();
  return () => {
    stopped = true;
    controller.abort();
  };
}
