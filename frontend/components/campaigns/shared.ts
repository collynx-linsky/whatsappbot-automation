// Shared style constants and lookups across the campaigns module's
// subcomponents (TemplatesSection, SegmentsSection, CampaignsSection, and
// their forms) — split out of what used to be one 862-line page.tsx.
import type { Campaign, CustomerSource, LeadStatus, TemplateStatus } from "@/types";

export const selectClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";
export const labelClass = "block text-sm font-medium text-zinc-700 dark:text-zinc-300";

export const TEMPLATE_STATUS_STYLE: Record<TemplateStatus, string> = {
  draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  pending_approval: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  approved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

export const CAMPAIGN_STATUS_STYLE: Record<Campaign["status"], string> = {
  draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  scheduled: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  sending: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  sent: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
  cancelled: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

export const LEAD_STATUSES: LeadStatus[] = [
  "new",
  "contacted",
  "qualified",
  "proposal",
  "converted",
  "lost",
];
export const CUSTOMER_SOURCES: CustomerSource[] = [
  "whatsapp",
  "website",
  "referral",
  "walk_in",
  "campaign",
  "other",
];
