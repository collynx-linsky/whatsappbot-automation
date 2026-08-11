// WhatsAppBusinessAI — Shared frontend types (mirrors backend serializers)

export type Role = "super_admin" | "business_owner" | "manager" | "staff";

export interface User {
  id: string;
  email: string;
  phone: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
  tenant_id: string | null;
  tenant_name: string | null;
  is_active: boolean;
  date_joined: string;
}

export type TenantStatus = "trial" | "active" | "suspended" | "cancelled";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  status: TenantStatus;
  plan: string | null;
  plan_name: string | null;
  business_count: number;
  trial_ends_at: string | null;
  subscription_ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Business {
  id: string;
  tenant: string;
  name: string;
  legal_name: string;
  description: string;
  category: string;
  phone: string;
  email: string;
  website: string;
  address: string;
  city: string;
  country: string;
  timezone: string;
  currency: string;
  logo: string | null;
  opening_hours: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Paginated<T> {
  status: string;
  count: number;
  total_pages: number;
  current_page: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// `POST /auth/login/` never returns real tokens directly — MFA is mandatory
// for every role (no exceptions). It returns a short-lived (10 min),
// purpose-tagged step-up token instead: `setup_token` the first time a user
// logs in (they haven't enrolled TOTP yet), `challenge_token` every time
// after that. See docs/mfa.md.
export type LoginResponse =
  | { mfa_setup_required: true; setup_token: string }
  | { mfa_required: true; challenge_token: string };

export interface MFASetupResponse {
  secret: string;
  // otpauth://totp/... URI — not an image. Render it as a QR code client-side.
  provisioning_uri: string;
}

export interface MFASetupConfirmResponse {
  access: string;
  refresh: string;
  // 10 single-use recovery codes, plaintext, shown exactly this once —
  // only their hash is ever persisted server-side.
  backup_codes: string[];
}

export interface MFAVerifyResponse {
  access: string;
  refresh: string;
}

export interface Session {
  jti: string;
  created_at: string;
  expires_at: string;
}

export interface OnboardBusinessPayload {
  tenant_name: string;
  business_name: string;
  business_category?: string;
  business_phone?: string;
  business_email?: string;
  business_country?: string;
  business_currency?: string;
  owner_email: string;
  owner_first_name: string;
  owner_last_name?: string;
}

export interface OnboardBusinessResponse {
  tenant: Tenant;
  owner: User;
  temporary_password: string;
}

export interface ApiErrorEnvelope {
  status: "error";
  message: string;
  errors: Record<string, string[]>;
  code: string;
}

export interface StaffMember {
  id: string;
  email: string;
  phone: string;
  first_name: string;
  last_name: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  date_joined: string;
}

export interface CreateStaffPayload {
  email: string;
  first_name: string;
  last_name?: string;
  phone?: string;
  role: "manager" | "staff";
}

export interface CreateStaffResponse {
  user: StaffMember;
  temporary_password: string;
}

export type LeadStatus = "new" | "contacted" | "qualified" | "proposal" | "converted" | "lost";
export type CustomerSource = "whatsapp" | "website" | "referral" | "walk_in" | "campaign" | "other";

export interface Customer {
  id: string;
  tenant: string;
  name: string;
  phone: string;
  email: string;
  location: string;
  tags: string[];
  source: CustomerSource;
  status: LeadStatus;
  notes: string;
  marketing_opt_in: boolean;
  marketing_opt_in_at: string | null;
  last_interaction_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ProductStatus = "draft" | "active" | "archived";

export interface Product {
  id: string;
  tenant: string;
  name: string;
  sku: string;
  description: string;
  category: string;
  price: string;
  currency: string;
  stock: number;
  is_available: boolean;
  status: ProductStatus;
  is_orderable: boolean;
  image: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateProductPayload {
  name: string;
  sku?: string;
  category?: string;
  price: string;
  currency?: string;
  stock?: number;
}

export type OrderStatus = "pending" | "confirmed" | "processing" | "ready" | "delivered" | "cancelled";

export interface OrderItemRecord {
  id: string;
  product: string;
  product_name: string;
  unit_price: string;
  quantity: number;
  subtotal: string;
}

export interface Order {
  id: string;
  tenant: string;
  customer: string;
  customer_name: string;
  customer_phone: string;
  conversation: string | null;
  status: OrderStatus;
  total_amount: string;
  currency: string;
  notes: string;
  confirmed_by: string | null;
  confirmed_by_name: string | null;
  confirmed_at: string | null;
  items: OrderItemRecord[];
  created_at: string;
  updated_at: string;
}

export interface CreateOrderPayload {
  customer: string;
  conversation?: string | null;
  notes?: string;
  items: { product: string; quantity: number }[];
}

// ── Inbox: conversations & messages ─────────────────────────
export type ConversationStatus = "open" | "pending" | "resolved" | "closed";
export type ConversationChannel = "whatsapp";

export interface Conversation {
  id: string;
  tenant: string;
  customer: string;
  customer_name: string;
  customer_phone: string;
  channel: ConversationChannel;
  status: ConversationStatus;
  assigned_to: string | null;
  assigned_to_name: string | null;
  // The AI-handoff toggle — there's no separate field for it, this IS it.
  ai_enabled: boolean;
  tags: string[];
  last_message_preview: string;
  last_message_at: string | null;
  // Read-only — no "mark read" endpoint exists server-side, so this can
  // never be reset from the client. Display only.
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateConversationPayload {
  customer: string;
  channel?: ConversationChannel;
  status?: ConversationStatus;
  assigned_to?: string | null;
  ai_enabled?: boolean;
  tags?: string[];
}

export interface ConversationAssignment {
  id: string;
  conversation: string;
  user: string;
  user_name: string;
  assigned_by: string | null;
  assigned_at: string;
  unassigned_at: string | null;
}

export type SenderType = "customer" | "staff" | "ai" | "system" | "campaign";
export type MessageDirection = "inbound" | "outbound";
export type MessageType = "text" | "image" | "document" | "audio" | "video" | "location";
export type MessageStatus = "pending" | "sent" | "delivered" | "read" | "failed";

export interface MessageAttachment {
  id: string;
  message: string;
  file: string;
  file_name: string;
  file_type: string;
  file_size: number;
  created_at: string;
}

export interface Message {
  id: string;
  tenant: string;
  conversation: string;
  sender_type: SenderType;
  sender_user: string | null;
  sender_name: string | null;
  direction: MessageDirection;
  message_type: MessageType;
  content: string;
  status: MessageStatus;
  external_message_id: string;
  attachments: MessageAttachment[];
  created_at: string;
}

// ── Analytics ────────────────────────────────────────────────
// Mirrors apps.analytics.services.business_dashboard() / .platform_dashboard()
// exactly — every metric is computed live server-side, nothing is stored.
// See docs/analytics.md.

export type FunnelCounts = Record<LeadStatus, number>;

export interface ConversationCounts {
  open: number;
  pending: number;
  resolved: number;
  closed: number;
  total: number;
}

export interface MessageCounts {
  total: number;
  by_sender_type: Record<SenderType, number>;
}

export interface OrderRevenue {
  by_status: Record<OrderStatus, number>;
  // Grouped by currency, never summed across currencies — a tenant's
  // orders aren't guaranteed to share one. Values are decimal strings, as
  // rendered by DRF's DecimalField, e.g. {"KES": "45000.00"}.
  revenue_by_currency: Record<string, string>;
}

export interface AIPerformance {
  ai_replies_sent: number;
  handoffs: number;
}

export interface ResponseTime {
  average_seconds: number | null;
  sample_count: number;
}

export interface TopQuestion {
  text: string;
  count: number;
}

export interface BusinessDashboard {
  funnel: FunnelCounts;
  conversations: ConversationCounts;
  messages: MessageCounts;
  orders: OrderRevenue;
  ai: AIPerformance;
  response_time: ResponseTime;
  top_questions: TopQuestion[];
}

export interface TenantCounts {
  trial: number;
  active: number;
  suspended: number;
  cancelled: number;
  total: number;
}

export type UserCounts = Record<Role, number> & { total: number };

export interface SignupTrendPoint {
  date: string;
  count: number;
}

export interface PlatformDashboard {
  tenants: TenantCounts;
  businesses: { total: number };
  users: UserCounts;
  conversations: { total: number };
  messages: { total: number };
  orders: { total: number; revenue_by_currency: Record<string, string> };
  signup_trend: SignupTrendPoint[];
}

// ── AI assistant settings ───────────────────────────────────
// Mirrors apps.ai.models.AISettings / AISettingsSerializer exactly. See
// docs/ai.md. Singleton per tenant — no id needed in the URL.
export type AIMode = "ai" | "human" | "hybrid";
export type AITone = "friendly" | "professional" | "casual" | "formal";
export type AIProvider = "openai" | "anthropic";

export interface AISettings {
  id: string;
  tenant: string;
  business: string;
  assistant_name: string;
  system_prompt: string;
  language: string;
  tone: AITone;
  welcome_message: string;
  fallback_message: string;
  max_response_length: number;
  mode: AIMode;
  ai_enabled: boolean;
  human_handoff_enabled: boolean;
  confidence_threshold: number;
  handoff_keywords: string[];
  provider: AIProvider;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export type UpdateAISettingsPayload = Partial<
  Omit<AISettings, "id" | "tenant" | "business" | "created_at" | "updated_at">
>;

export interface AITestResult {
  handed_off: boolean;
  reason?: string | null;
  reply?: string | null;
  confidence?: number | null;
}

// ── Knowledge base (RAG) ────────────────────────────────────
// Mirrors apps.knowledge.serializers exactly. See docs/rag.md. Unlike
// Conversation/Message/Order (tenant-scoped only), KnowledgeDocument is
// FK'd to Business directly, so creating one needs an explicit business id.
export type KnowledgeSourceType = "upload" | "text";
export type KnowledgeDocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface KnowledgeDocument {
  id: string;
  tenant: string;
  business: string;
  title: string;
  source_type: KnowledgeSourceType;
  file: string | null;
  status: KnowledgeDocumentStatus;
  error_message: string;
  chunk_count: number;
  embedded_chunk_count: number;
  uploaded_by: string | null;
  created_at: string;
  updated_at: string;
}

// Sent as multipart/form-data (file upload), not JSON — see lib/api.ts.
export interface CreateKnowledgeDocumentPayload {
  business: string;
  title: string;
  source_type: KnowledgeSourceType;
  file?: File;
  raw_text?: string;
}

export interface KnowledgeChunk {
  id: string;
  chunk_index: number;
  content: string;
  is_embedded: boolean;
  created_at: string;
}

// ── Marketing campaigns ─────────────────────────────────────
// Mirrors apps.campaigns.serializers exactly. See docs/campaigns.md.
// Compliance is structural here, not just UI convention: a Segment always
// filters to Customer.marketing_opt_in=True (see customer_count below),
// and a Campaign can only actually send with an `approved` Template — the
// backend enforces both at send time, not just creation.
export type TemplateCategory = "marketing" | "utility" | "authentication";
export type TemplateStatus = "draft" | "pending_approval" | "approved" | "rejected";

export interface MessageTemplate {
  id: string;
  tenant: string;
  business: string;
  created_by: string | null;
  name: string;
  whatsapp_template_name: string;
  category: TemplateCategory;
  language_code: string;
  body_text: string;
  status: TemplateStatus;
  rejection_reason: string;
  // Count of distinct {{n}} placeholders in body_text — server-computed.
  variable_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateMessageTemplatePayload {
  business: string;
  name: string;
  whatsapp_template_name?: string;
  category?: TemplateCategory;
  language_code?: string;
  body_text: string;
}

export interface SegmentFilters {
  statuses?: LeadStatus[];
  sources?: CustomerSource[];
  tags?: string[];
}

export interface Segment {
  id: string;
  tenant: string;
  business: string;
  created_by: string | null;
  name: string;
  description: string;
  filters: SegmentFilters;
  // Re-evaluated live on every read — always opted-in customers only.
  customer_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateSegmentPayload {
  business: string;
  name: string;
  description?: string;
  filters?: SegmentFilters;
}

export interface SegmentPreview {
  customer_count: number;
  sample: { id: string; name: string; phone: string }[];
}

export type CampaignStatus = "draft" | "scheduled" | "sending" | "sent" | "failed" | "cancelled";

export interface Campaign {
  id: string;
  tenant: string;
  business: string;
  segment: string;
  template: string;
  created_by: string | null;
  name: string;
  // Positional {{1}}, {{2}}, ... substitutions — same for every recipient,
  // no per-recipient personalization this phase (see docs/campaigns.md).
  template_variables: string[];
  status: CampaignStatus;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateCampaignPayload {
  business: string;
  segment: string;
  template: string;
  name: string;
  template_variables?: string[];
  scheduled_at?: string | null;
}

export type CampaignRecipientStatus = "pending" | "sent" | "failed" | "skipped";

export interface CampaignRecipient {
  id: string;
  customer: string;
  customer_name: string;
  customer_phone: string;
  status: CampaignRecipientStatus;
  skip_reason: string;
  error_message: string;
  sent_at: string | null;
  created_at: string;
}

// ── Billing ──────────────────────────────────────────────────
// Mirrors apps.billing.services.usage_summary() / InvoiceSerializer
// exactly. See docs/billing.md. No Subscription model — Tenant itself
// carries plan/status; no payment gateway — an Invoice records what's
// owed, nothing charges a card.
export type UsageLimitName = "users" | "whatsapp_accounts" | "customers" | "ai_messages" | "campaign_sends";

export interface UsageLimit {
  used: number;
  // A Plan limit of 0 means unlimited — see `unlimited` below, which is
  // the honest signal to render rather than treating limit=0 as "no room."
  limit: number;
  unlimited: boolean;
}

export interface UsageSummary {
  plan: string | null;
  limits: Partial<Record<UsageLimitName, UsageLimit>>;
}

export type InvoiceStatus = "draft" | "issued" | "paid" | "overdue" | "void";

export interface Invoice {
  id: string;
  tenant: string;
  invoice_number: string;
  period_start: string;
  period_end: string;
  // Snapshotted at generation time, not a live Plan FK — a later plan
  // rename/price change never rewrites a historical invoice.
  plan_name: string;
  amount: string;
  currency: string;
  status: InvoiceStatus;
  issued_at: string | null;
  due_at: string | null;
  paid_at: string | null;
  notes: string;
  created_at: string;
}

export interface GenerateInvoicePayload {
  tenant: string;
  period_start?: string;
}

// ── WhatsApp account connection ─────────────────────────────
// Mirrors apps.whatsapp.serializers.WhatsAppAccountSerializer exactly.
// `access_token` is write-only server-side — deliberately absent from
// this read type, since the API never returns it (see docs/security.md).
export type WhatsAppAccountStatus = "pending" | "connected" | "disconnected" | "error";

export interface WhatsAppAccount {
  id: string;
  tenant: string;
  business: string;
  display_name: string;
  phone_number: string;
  phone_number_id: string;
  business_account_id: string;
  status: WhatsAppAccountStatus;
  is_connected: boolean;
  connected_at: string | null;
  last_sync_at: string | null;
  last_error: string;
  created_at: string;
  updated_at: string;
}

// ── Public marketing site ───────────────────────────────────
// Mirrors apps.tenants.serializers.PublicPlanSerializer — the slim,
// no-auth-required subset of Plan shown on the public pricing section.
// Deliberately excludes max_storage_mb (not actually enforced anywhere
// yet — see docs/billing.md) and is_active/is_default (internal only).
export interface PublicPlan {
  id: string;
  name: string;
  slug: string;
  description: string;
  price_monthly: string;
  currency: string;
  max_users: number;
  max_whatsapp_accounts: number;
  max_ai_messages_per_month: number;
  max_customers: number;
  max_campaigns_per_month: number;
  sort_order: number;
}

export interface CreateWhatsAppAccountPayload {
  business: string;
  display_name?: string;
  phone_number: string;
  phone_number_id: string;
  business_account_id: string;
  access_token: string;
}
