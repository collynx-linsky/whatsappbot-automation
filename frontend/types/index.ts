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

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
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
