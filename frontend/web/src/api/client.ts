/**
 * The ONLY place that talks to the network.
 *
 * LEARN:
 *  - Every call goes to /v1/... on our own origin; Vite forwards it to the Conductor.
 *  - The advisor's token is attached here, nowhere else.
 *  - A 401 means the sign-in expired: we tell the app (onUnauthorized) and it signs out.
 *  - Every error keeps the X-Trace-Id, so the screen can show it and you can search the logs.
 */
import type { Login } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly traceId: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let token: string | null = null;
let onUnauthorized: () => void = () => {};

export function setToken(value: string | null): void {
  token = value;
}

export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const init: RequestInit = { method, headers };
  if (body !== undefined) init.body = JSON.stringify(body);
  if (signal) init.signal = signal;
  const res = await fetch(path, init);
  const traceId = res.headers.get("X-Trace-Id");
  if (res.status === 401 && token) onUnauthorized();
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) detail = "Some fields are not valid.";
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(detail, res.status, traceId);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>("GET", path, undefined, signal),
  post: <T>(path: string, body: unknown) => request<T>("POST", path, body),
  login: (username: string, password: string) => request<Login>("POST", "/v1/auth/login", { username, password }),
};
