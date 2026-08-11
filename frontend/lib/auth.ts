// WhatsAppBusinessAI — Token storage
//
// JWTs live in localStorage (client-only). There is no server-side session,
// so route guarding is done per-page (check token presence in a client
// effect) rather than via Next.js middleware/proxy — see docs/development.md
// for why (this app has no dynamic route segments yet, and localStorage
// tokens aren't visible to the server anyway).
import type { User } from "@/types";

const ACCESS_KEY = "waba_access_token";
const REFRESH_KEY = "waba_refresh_token";
const USER_KEY = "waba_user";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  return raw ? (JSON.parse(raw) as User) : null;
}

export function setSession(access: string, refresh: string, user: User): void {
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function setAccessToken(access: string): void {
  window.localStorage.setItem(ACCESS_KEY, access);
}

// Used by the MFA setup/verify flow: real access+refresh tokens exist at
// this point, but the User object doesn't yet (mfaSetupConfirm/mfaVerify
// only return tokens) — store the tokens now, call setSession() once
// getMe() resolves to also persist the user and complete the session.
export function setTokens(access: string, refresh: string): void {
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(USER_KEY);
}

export function dashboardPathForRole(role: User["role"]): string {
  return role === "super_admin" ? "/admin" : "/dashboard";
}

// ── MFA pending token ────────────────────────────────────────
//
// Between `POST /auth/login/` and completing the MFA setup/challenge step,
// we're holding a purpose-tagged step-up token, not a real session — it's
// short-lived (10 min) and only ever useful in the tab that received it, so
// sessionStorage (not localStorage) is the deliberate choice here: it
// shouldn't linger the way a real session does.
const PENDING_TOKEN_KEY = "waba_pending_mfa_token";

export function setPendingToken(token: string): void {
  window.sessionStorage.setItem(PENDING_TOKEN_KEY, token);
}

export function getPendingToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(PENDING_TOKEN_KEY);
}

export function clearPendingToken(): void {
  window.sessionStorage.removeItem(PENDING_TOKEN_KEY);
}
