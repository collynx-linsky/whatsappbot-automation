"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Meter } from "@/components/Meter";
import { ApiError, getUsageSummary, listInvoices } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { Invoice, InvoiceStatus, UsageLimitName, UsageSummary } from "@/types";

const LIMIT_LABEL: Record<UsageLimitName, string> = {
  users: "Team members",
  whatsapp_accounts: "WhatsApp accounts",
  customers: "Customers",
  ai_messages: "AI messages this month",
  campaign_sends: "Campaign sends this month",
};
const LIMIT_ORDER: UsageLimitName[] = [
  "users",
  "whatsapp_accounts",
  "customers",
  "ai_messages",
  "campaign_sends",
];

const INVOICE_STATUS_STYLE: Record<InvoiceStatus, string> = {
  draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  issued: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  paid: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  overdue: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
  void: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

export default function BillingPage() {
  const { user, ready } = useRequireAuth();
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canViewInvoices = user?.role === "business_owner" || user?.role === "manager";

  useEffect(() => {
    if (!ready) return;
    getUsageSummary()
      .then((res) => setUsage(res))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load usage."));
    if (canViewInvoices) {
      listInvoices()
        .then((res) => setInvoices(res.results))
        .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load invoices."));
    }
  }, [ready, canViewInvoices]);

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  return (
    <DashboardShell
      user={user}
      title="Billing"
      nav={[
        { label: "Overview", href: "/dashboard" },
        { label: "Products & Orders", href: "/dashboard/products" },
        { label: "Inbox", href: "/dashboard/inbox" },
        { label: "AI Assistant", href: "/dashboard/ai" },
        { label: "Knowledge Base", href: "/dashboard/knowledge" },
        { label: "Campaigns", href: "/dashboard/campaigns" },
        { label: "WhatsApp", href: "/dashboard/whatsapp" },
        { label: "Billing", href: "/dashboard/billing" },
        { label: "Analytics", href: "/dashboard/analytics" },
      ]}
    >
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Plan Usage
          </h2>
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            {!usage ? (
              <p className="text-sm text-zinc-500">Loading…</p>
            ) : usage.plan === null ? (
              <p className="text-sm text-zinc-500">No plan assigned to this account yet.</p>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Plan: <span className="font-medium text-zinc-900 dark:text-zinc-100">{usage.plan}</span>
                </p>
                {LIMIT_ORDER.map((key) => {
                  const limit = usage.limits[key];
                  if (!limit) return null;
                  return (
                    <Meter
                      key={key}
                      label={LIMIT_LABEL[key]}
                      used={limit.used}
                      limit={limit.limit}
                      unlimited={limit.unlimited}
                    />
                  );
                })}
              </div>
            )}
          </div>
        </section>

        {canViewInvoices && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Invoices
            </h2>
            <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
              No payment gateway is connected — an invoice records what&apos;s owed, nothing charges a
              card automatically.
            </p>
            <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                  <tr>
                    <th className="px-4 py-2 font-medium">Invoice</th>
                    <th className="px-4 py-2 font-medium">Period</th>
                    <th className="px-4 py-2 font-medium">Plan</th>
                    <th className="px-4 py-2 font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices?.map((inv) => (
                    <tr key={inv.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{inv.invoice_number}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {inv.period_start} – {inv.period_end}
                      </td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{inv.plan_name}</td>
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                        {inv.currency} {inv.amount}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${INVOICE_STATUS_STYLE[inv.status]}`}
                        >
                          {inv.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {inv.due_at ? new Date(inv.due_at).toLocaleDateString() : "—"}
                      </td>
                    </tr>
                  ))}
                  {invoices?.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-zinc-500">
                        No invoices yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </DashboardShell>
  );
}
