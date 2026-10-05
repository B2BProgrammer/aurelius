/**
 * Sign-in state.
 *
 * LEARN: the token lives in memory and in sessionStorage (cleared when the tab
 * closes), never in localStorage. We read its expiry ("exp") and sign out on
 * time, and on any 401 from the server. In a production deployment the safer
 * pattern is an httpOnly cookie set by the server, so page scripts can't read
 * the token at all; the Conductor's JWT design makes that a small change.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, setToken, setUnauthorizedHandler } from "../api/client";

interface Session {
  token: string;
  user: string;
  expiresAt: number; // ms since epoch
}

interface AuthState {
  session: Session | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: (reason?: string) => void;
  notice: string | null;
}

const KEY = "atrium.session";
const AuthContext = createContext<AuthState | null>(null);

function readStored(): Session | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return s.expiresAt > Date.now() + 5_000 ? s : null;
  } catch {
    return null;
  }
}

/** Reads "exp" from a JWT (display only: the SERVER verifies the signature). */
export function jwtExpiry(token: string): number | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: number };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const s = readStored();
    setToken(s?.token ?? null);
    return s;
  });
  const [notice, setNotice] = useState<string | null>(null);

  const signOut = useCallback((reason?: string) => {
    setToken(null);
    try {
      sessionStorage.removeItem(KEY);
    } catch {
      // storage unavailable: nothing to clear
    }
    setSession(null);
    setNotice(reason ?? null);
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    const expiresAt = jwtExpiry(res.access_token) ?? Date.now() + res.expires_in * 1000;
    const s: Session = { token: res.access_token, user: res.user, expiresAt };
    setToken(s.token);
    try {
      sessionStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      // private mode: the session lasts until this tab reloads
    }
    setNotice(null);
    setSession(s);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => signOut("Your sign-in expired. Sign in again."));
  }, [signOut]);

  useEffect(() => {
    if (!session) return;
    const ms = session.expiresAt - Date.now();
    const timer = setTimeout(() => signOut("Your sign-in expired. Sign in again."), Math.max(ms, 0));
    return () => clearTimeout(timer);
  }, [session, signOut]);

  const value = useMemo(() => ({ session, signIn, signOut, notice }), [session, signIn, signOut, notice]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
