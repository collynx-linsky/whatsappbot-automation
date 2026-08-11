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
