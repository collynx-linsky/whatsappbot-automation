// WhatsAppBusinessAI — Typed API client
//
// Wraps fetch() against the Django backend: attaches the JWT, retries once
// on 401 after a silent refresh, and normalizes the backend's error
// envelope ({status, message, errors, code}) into a typed ApiError.
import type {
  AISettings,
  AITestResult,
  ApiErrorEnvelope,
  Business,
  BusinessDashboard,
  Campaign,
  CampaignRecipient,
  CampaignStatus,
  Conversation,
  CreateCampaignPayload,
  CreateKnowledgeDocumentPayload,
  CreateMessageTemplatePayload,
  CreateSegmentPayload,
  CreateWhatsAppAccountPayload,
  ConversationAssignment,
  ConversationStatus,
  CreateConversationPayload,
  CreateOrderPayload,
  CreateProductPayload,
  CreateStaffPayload,
  CreateStaffResponse,
  Customer,
  GenerateInvoicePayload,
  Invoice,
  KnowledgeChunk,
  KnowledgeDocument,
  LoginResponse,
  MessageTemplate,
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
  PlatformDashboard,
  Product,
  PublicPlan,
  Segment,
  SegmentPreview,
  Session,
  StaffMember,
  Tenant,
  UpdateAISettingsPayload,
  UsageSummary,
  User,
  WhatsAppAccount,
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
  // A FormData body (file upload) must NOT get an explicit Content-Type —
  // the browser sets multipart/form-data with the right boundary itself.
  // Every other caller in this codebase sends JSON, so this only changes
  // behavior for the one FormData case.
  const isFormData = typeof FormData !== "undefined" && rest.body instanceof FormData;

  const doFetch = async (token: string | null) => {
    const finalHeaders: HeadersInit = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

  // Read as text first, not res.json() directly — 204 isn't the only
  // legitimate empty-body success response in this API (e.g. logout's
  // 205 Reset Content also has none), and calling .json() on an empty
  // body throws "Unexpected end of JSON input" rather than returning
  // undefined. A real prior bug: this crashed logout() with no try/catch
  // above it to swallow it, so the redirect to /login never ran — caught
  // by the Playwright e2e suite, not by eslint/tsc/build. See docs/testing.md.
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, (data as ApiErrorEnvelope) ?? {
      status: "error",
      message: `Request failed with status ${res.status}.`,
      errors: {},
      code: "unknown_error",
    });
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
  const text = await res.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, (data as ApiErrorEnvelope) ?? {
      status: "error",
      message: `Request failed with status ${res.status}.`,
      errors: {},
      code: "unknown_error",
    });
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

// ── Public marketing site ───────────────────────────────────
// No auth — this is what the public "/" landing page's pricing section
// reads, so real, live Plan data shows up there instead of numbers
// hardcoded in the frontend that could drift from what's actually
// configured.
export function getPublicPlans(): Promise<Paginated<PublicPlan>> {
  return apiFetch<Paginated<PublicPlan>>("/tenants/plans/public/", { auth: false });
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

// ── Analytics ────────────────────────────────────────────────
// Every number is computed live server-side on each request — no polling
// needed here (unlike the inbox), the caller just re-fetches on demand
// (e.g. when the date range changes).
export function getAnalyticsDashboard(params?: {
  start?: string;
  end?: string;
}): Promise<BusinessDashboard> {
  return apiFetch<BusinessDashboard>(`/analytics/dashboard/${toQueryString(params ?? {})}`);
}

export function getPlatformAnalytics(): Promise<PlatformDashboard> {
  return apiFetch<PlatformDashboard>("/analytics/platform/");
}

// ── AI assistant settings ───────────────────────────────────
// Singleton per tenant — no id in the URL, unlike every other tenant-scoped
// resource in this API (matches the backend: lazily created on first GET).
export function getAISettings(): Promise<AISettings> {
  return apiFetch<AISettings>("/ai/settings/");
}

export function updateAISettings(payload: UpdateAISettingsPayload): Promise<AISettings> {
  return apiFetch<AISettings>("/ai/settings/", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// Onboarding step 7 "test your AI" — runs the real handoff-check +
// prompt-building logic against ad-hoc text, without touching any real
// Conversation/Message. Throttled server-side (real provider cost).
export function testAI(message: string): Promise<AITestResult> {
  return apiFetch<AITestResult>("/ai/test/", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

// ── Knowledge base (RAG) ────────────────────────────────────
export function listKnowledgeDocuments(): Promise<Paginated<KnowledgeDocument>> {
  return apiFetch<Paginated<KnowledgeDocument>>("/knowledge/documents/");
}

// multipart/form-data, not JSON — the only file upload in this codebase so
// far (see apiFetch's FormData handling). Processing (extract → chunk →
// embed) runs async via Celery; the response comes back before it finishes,
// so the caller should poll listKnowledgeDocuments() to watch status settle.
export function createKnowledgeDocument(
  payload: CreateKnowledgeDocumentPayload,
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.set("business", payload.business);
  form.set("title", payload.title);
  form.set("source_type", payload.source_type);
  if (payload.file) form.set("file", payload.file);
  if (payload.raw_text) form.set("raw_text", payload.raw_text);
  return apiFetch<KnowledgeDocument>("/knowledge/documents/", {
    method: "POST",
    body: form,
  });
}

export function deleteKnowledgeDocument(id: string): Promise<void> {
  return apiFetch<void>(`/knowledge/documents/${id}/`, { method: "DELETE" });
}

export function listKnowledgeChunks(documentId: string): Promise<Paginated<KnowledgeChunk>> {
  return apiFetch<Paginated<KnowledgeChunk>>(`/knowledge/documents/${documentId}/chunks/`);
}

// ── Marketing campaigns ──────────────────────────────────────
// Templates
export function listTemplates(params?: {
  status?: string;
  category?: string;
}): Promise<Paginated<MessageTemplate>> {
  return apiFetch<Paginated<MessageTemplate>>(`/campaigns/templates/${toQueryString(params ?? {})}`);
}

export function createTemplate(payload: CreateMessageTemplatePayload): Promise<MessageTemplate> {
  return apiFetch<MessageTemplate>("/campaigns/templates/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTemplate(
  id: string,
  payload: Partial<Pick<MessageTemplate, "status" | "whatsapp_template_name" | "rejection_reason">>,
): Promise<MessageTemplate> {
  return apiFetch<MessageTemplate>(`/campaigns/templates/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// Segments
export function listSegments(): Promise<Paginated<Segment>> {
  return apiFetch<Paginated<Segment>>("/campaigns/segments/");
}

export function createSegment(payload: CreateSegmentPayload): Promise<Segment> {
  return apiFetch<Segment>("/campaigns/segments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSegment(id: string): Promise<void> {
  return apiFetch<void>(`/campaigns/segments/${id}/`, { method: "DELETE" });
}

export function previewSegment(id: string): Promise<SegmentPreview> {
  return apiFetch<SegmentPreview>(`/campaigns/segments/${id}/preview/`);
}

// Campaigns
export function listCampaigns(params?: { status?: CampaignStatus }): Promise<Paginated<Campaign>> {
  return apiFetch<Paginated<Campaign>>(`/campaigns/${toQueryString(params ?? {})}`);
}

export function createCampaign(payload: CreateCampaignPayload): Promise<Campaign> {
  return apiFetch<Campaign>("/campaigns/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Queues the real send (async, via Celery) — the returned Campaign reflects
// whatever state it's in the instant the queue call returns (usually
// "scheduled"), not the final outcome. Poll listCampaigns() to watch it
// settle to sent/failed, same pattern as the knowledge base's processing.
export function sendCampaign(id: string): Promise<Campaign> {
  return apiFetch<Campaign>(`/campaigns/${id}/send/`, { method: "POST" });
}

export function listCampaignRecipients(id: string): Promise<Paginated<CampaignRecipient>> {
  return apiFetch<Paginated<CampaignRecipient>>(`/campaigns/${id}/recipients/`);
}

// ── Billing ──────────────────────────────────────────────────
export function getUsageSummary(): Promise<UsageSummary> {
  return apiFetch<UsageSummary>("/billing/usage/");
}

export function listInvoices(): Promise<Paginated<Invoice>> {
  return apiFetch<Paginated<Invoice>>("/billing/invoices/");
}

// Super admin only — no automated payment gateway/webhook exists to
// trigger this, so it's a manual per-tenant action (see docs/billing.md).
export function generateInvoice(payload: GenerateInvoicePayload): Promise<Invoice> {
  return apiFetch<Invoice>("/billing/invoices/generate/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── WhatsApp account connection ─────────────────────────────
export function listWhatsAppAccounts(): Promise<Paginated<WhatsAppAccount>> {
  return apiFetch<Paginated<WhatsAppAccount>>("/whatsapp/accounts/");
}

export function createWhatsAppAccount(
  payload: CreateWhatsAppAccountPayload,
): Promise<WhatsAppAccount> {
  return apiFetch<WhatsAppAccount>("/whatsapp/accounts/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Reconnecting with a fresh access_token (e.g. after Meta rotates/revokes
// it) goes through the same PATCH — the field is write-only and never
// echoed back, matching the create path.
export function updateWhatsAppAccount(
  id: string,
  payload: Partial<
    Pick<
      WhatsAppAccount,
      "display_name" | "phone_number" | "phone_number_id" | "business_account_id"
    >
  > & { access_token?: string },
): Promise<WhatsAppAccount> {
  return apiFetch<WhatsAppAccount>(`/whatsapp/accounts/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
