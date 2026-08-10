// WhatsAppBusinessAI — Typed API client
//
// Wraps fetch() against the Django backend: attaches the JWT, retries once
// on 401 after a silent refresh, and normalizes the backend's error
// envelope ({status, message, errors, code}) into a typed ApiError.
import type {
  ApiErrorEnvelope,
  Business,
  LoginResponse,
  OnboardBusinessPayload,
  OnboardBusinessResponse,
  Paginated,
  Tenant,
  User,
} from "@/types";
import { clearSession, getAccessToken, getRefreshToken, setAccessToken, setSession } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  errors: Record<string, string[]>;

  constructor(status: number, envelope: ApiErrorEnvelope) {
    super(envelope.message);
    this.status = status;
    this.code = envelope.code;
    this.errors = envelope.errors;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  const res = await fetch(`${API_BASE}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!res.ok) return null;

  const data = (await res.json()) as { access: string };
  setAccessToken(data.access);
  return data.access;
}

interface RequestOptions extends RequestInit {
  auth?: boolean; // defaults to true
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { auth = true, headers, ...rest } = options;

  const doFetch = async (token: string | null) => {
    const finalHeaders: HeadersInit = {
      "Content-Type": "application/json",
      ...headers,
      ...(auth && token ? { Authorization: `Bearer ${token}` } : {}),
    };
    return fetch(`${API_BASE}${path}`, { ...rest, headers: finalHeaders });
  };

  let res = await doFetch(auth ? getAccessToken() : null);

  if (auth && res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetch(newToken);
    } else {
      clearSession();
    }
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json();
  if (!res.ok) {
    throw new ApiError(res.status, data as ApiErrorEnvelope);
  }
  return data as T;
}

// ── Auth ─────────────────────────────────────────────────────
export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/auth/login/", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password }),
  });
  setSession(data.access, data.refresh, data.user);
  return data;
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiFetch("/auth/logout/", { method: "POST", body: JSON.stringify({ refresh }) });
    }
  } finally {
    clearSession();
  }
}

export function getMe(): Promise<User> {
  return apiFetch<User>("/auth/me/");
}

export function forgotPassword(email: string): Promise<{ detail: string }> {
  return apiFetch("/auth/forgot-password/", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, new_password: string): Promise<{ detail: string }> {
  return apiFetch("/auth/reset-password/", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ token, new_password }),
  });
}

// ── Tenants (super admin) ───────────────────────────────────
export function listTenants(): Promise<Paginated<Tenant>> {
  return apiFetch<Paginated<Tenant>>("/tenants/");
}

export function onboardBusiness(
  payload: OnboardBusinessPayload,
): Promise<OnboardBusinessResponse> {
  return apiFetch<OnboardBusinessResponse>("/tenants/onboard/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function suspendTenant(id: string): Promise<Tenant> {
  return apiFetch<Tenant>(`/tenants/${id}/suspend/`, { method: "POST" });
}

export function activateTenant(id: string): Promise<Tenant> {
  return apiFetch<Tenant>(`/tenants/${id}/activate/`, { method: "POST" });
}

// ── Businesses ───────────────────────────────────────────────
export function listBusinesses(): Promise<Paginated<Business>> {
  return apiFetch<Paginated<Business>>("/businesses/");
}

export function updateBusiness(id: string, payload: Partial<Business>): Promise<Business> {
  return apiFetch<Business>(`/businesses/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
