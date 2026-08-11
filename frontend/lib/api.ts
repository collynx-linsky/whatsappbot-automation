// WhatsAppBusinessAI — Typed API client
//
// Wraps fetch() against the Django backend: attaches the JWT, retries once
// on 401 after a silent refresh, and normalizes the backend's error
// envelope ({status, message, errors, code}) into a typed ApiError.
import type {
  ApiErrorEnvelope,
  Business,
  Conversation,
  ConversationAssignment,
  ConversationStatus,
  CreateConversationPayload,
  CreateOrderPayload,
  CreateProductPayload,
  CreateStaffPayload,
  CreateStaffResponse,
  Customer,
  LoginResponse,
  Message,
  MessageType,
  MFASetupConfirmResponse,
  MFASetupResponse,
  MFAVerifyResponse,
  OnboardBusinessPayload,
  OnboardBusinessResponse,
  Order,
  OrderStatus,
  Paginated,
  Product,
  Session,
  StaffMember,
  Tenant,
  User,
} from "@/types";
import { clearSession, getAccessToken, getRefreshToken, setAccessToken } from "./auth";

// Builds a "?key=value&..." query string, skipping undefined/null/empty
// values so callers can pass a params object without conditionals.
function toQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== "",
  );
  if (entries.length === 0) return "";
  const search = new URLSearchParams();
  for (const [k, v] of entries) search.set(k, String(v));
  return `?${search.toString()}`;
}

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
//
// `login()` never yields a real session directly — MFA is mandatory for
// every role, so the backend always returns a step-up token instead (see
// LoginResponse in @/types). The caller (the login page) is responsible for
// stashing that token and continuing through the MFA setup/verify flow.
export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login/", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password }),
  });
}

// The three MFA endpoints authenticate with a short-lived (10 min)
// purpose-tagged token, not the normal access token — so they can't go
// through apiFetch()'s Authorization header / silent-refresh-retry logic.
// A 401/403 here means "the step-up token expired or is wrong-purpose,
// start over," never "refresh and retry."
async function pendingTokenFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new ApiError(res.status, data as ApiErrorEnvelope);
  }
  return data as T;
}

export function mfaSetup(setupToken: string): Promise<MFASetupResponse> {
  return pendingTokenFetch<MFASetupResponse>("/auth/mfa/setup/", setupToken, {
    method: "POST",
  });
}

export function mfaSetupConfirm(
  setupToken: string,
  code: string,
): Promise<MFASetupConfirmResponse> {
  return pendingTokenFetch<MFASetupConfirmResponse>("/auth/mfa/setup/confirm/", setupToken, {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function mfaVerify(
  challengeToken: string,
  payload: { code?: string; backup_code?: string },
): Promise<MFAVerifyResponse> {
  return pendingTokenFetch<MFAVerifyResponse>("/auth/mfa/verify/", challengeToken, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSessions(): Promise<Session[]> {
  return apiFetch<Session[]>("/auth/sessions/");
}

export function revokeSession(jti: string): Promise<{ detail: string }> {
  return apiFetch<{ detail: string }>(`/auth/sessions/${jti}/revoke/`, {
    method: "POST",
  });
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

// ── Staff ────────────────────────────────────────────────────
export function listStaff(): Promise<Paginated<StaffMember>> {
  return apiFetch<Paginated<StaffMember>>("/staff/");
}

export function createStaff(payload: CreateStaffPayload): Promise<CreateStaffResponse> {
  return apiFetch<CreateStaffResponse>("/staff/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateStaff(
  id: string,
  payload: Partial<Pick<StaffMember, "role" | "is_active" | "first_name" | "last_name" | "phone">>,
): Promise<StaffMember> {
  return apiFetch<StaffMember>(`/staff/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ── Customers ────────────────────────────────────────────────
export function listCustomers(params?: {
  search?: string;
  status?: string;
  source?: string;
  page?: number;
}): Promise<Paginated<Customer>> {
  return apiFetch<Paginated<Customer>>(`/customers/${toQueryString(params ?? {})}`);
}

// ── Products ─────────────────────────────────────────────────
export function listProducts(): Promise<Paginated<Product>> {
  return apiFetch<Paginated<Product>>("/products/");
}

export function createProduct(payload: CreateProductPayload): Promise<Product> {
  return apiFetch<Product>("/products/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProduct(id: string, payload: Partial<CreateProductPayload>): Promise<Product> {
  return apiFetch<Product>(`/products/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ── Orders ───────────────────────────────────────────────────
export function listOrders(): Promise<Paginated<Order>> {
  return apiFetch<Paginated<Order>>("/orders/");
}

export function createOrder(payload: CreateOrderPayload): Promise<Order> {
  return apiFetch<Order>("/orders/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateOrderStatus(id: string, newStatus: OrderStatus): Promise<Order> {
  return apiFetch<Order>(`/orders/${id}/status/`, {
    method: "POST",
    body: JSON.stringify({ status: newStatus }),
  });
}

// ── Inbox: conversations & messages ─────────────────────────
//
// No real-time channel exists on the backend (no websockets/SSE) — the
// inbox page polls these endpoints on an interval rather than subscribing
// to anything.
export function listConversations(params?: {
  status?: ConversationStatus;
  assigned_to?: string;
  ai_enabled?: boolean;
  search?: string;
  ordering?: string;
  page?: number;
}): Promise<Paginated<Conversation>> {
  return apiFetch<Paginated<Conversation>>(`/conversations/${toQueryString(params ?? {})}`);
}

export function createConversation(payload: CreateConversationPayload): Promise<Conversation> {
  return apiFetch<Conversation>("/conversations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateConversation(
  id: string,
  payload: Partial<Pick<Conversation, "status" | "ai_enabled" | "tags">>,
): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// The dedicated assign endpoint, not a generic PATCH on `assigned_to` — it's
// the one that writes an AuditLog entry and a ConversationAssignment
// history row server-side.
export function assignConversation(id: string, userId: string | null): Promise<Conversation> {
  return apiFetch<Conversation>(`/conversations/${id}/assign/`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}

export function listConversationAssignments(
  id: string,
): Promise<Paginated<ConversationAssignment>> {
  return apiFetch<Paginated<ConversationAssignment>>(`/conversations/${id}/assignments/`);
}

export function listMessages(
  conversationId: string,
  params?: { page?: number },
): Promise<Paginated<Message>> {
  return apiFetch<Paginated<Message>>(
    `/messages/${toQueryString({ conversation: conversationId, ordering: "created_at", ...params })}`,
  );
}

// The backend only accepts sender_type: "staff" via this endpoint this
// phase (customer/AI messages arrive via the WhatsApp webhook/AI engine
// instead) — hardcoded here rather than exposed as a caller param.
export function sendMessage(
  conversation: string,
  content: string,
  messageType: MessageType = "text",
): Promise<Message> {
  return apiFetch<Message>("/messages/", {
    method: "POST",
    body: JSON.stringify({ conversation, sender_type: "staff", content, message_type: messageType }),
  });
}
