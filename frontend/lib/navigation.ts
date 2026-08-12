// WABA AI — Canonical dashboard navigation
//
// Single source of truth for the tenant-side nav — was previously copy-
// pasted identically into 9 separate page files (a real drift risk: add a
// 10th page and it's 9 files to remember to update, nothing catches a
// missed one). Every dashboard page now imports DASHBOARD_NAV instead of
// hardcoding it. DashboardShell also used to map icons by href in a
// separate lookup table; that's folded in here so a nav item and its icon
// can never drift apart.
//
// The /admin super-admin surface deliberately does NOT use this — it's a
// separate, single-route surface for a different role, not a tenant-side
// module (see core.permissions.IsSuperAdmin server-side; nothing here
// enforces that boundary, the backend does — this list is just what a
// tenant-side user sees, never a security control).
import {
  IconBook,
  IconCart,
  IconChart,
  IconChat,
  IconCreditCard,
  IconHome,
  IconMegaphone,
  IconPhone,
  IconSpark,
  type IconComponent,
} from "@/components/Icons";

export interface NavItem {
  label: string;
  href: string;
  icon: IconComponent;
}

export const DASHBOARD_NAV: NavItem[] = [
  { label: "Overview", href: "/dashboard", icon: IconHome },
  { label: "Products & Orders", href: "/dashboard/products", icon: IconCart },
  { label: "Inbox", href: "/dashboard/inbox", icon: IconChat },
  { label: "AI Assistant", href: "/dashboard/ai", icon: IconSpark },
  { label: "Knowledge Base", href: "/dashboard/knowledge", icon: IconBook },
  { label: "Campaigns", href: "/dashboard/campaigns", icon: IconMegaphone },
  { label: "WhatsApp", href: "/dashboard/whatsapp", icon: IconPhone },
  { label: "Billing", href: "/dashboard/billing", icon: IconCreditCard },
  { label: "Analytics", href: "/dashboard/analytics", icon: IconChart },
];
