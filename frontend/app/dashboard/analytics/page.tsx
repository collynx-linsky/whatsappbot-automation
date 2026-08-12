"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { BarList, BarListLegend, type BarListItem } from "@/components/BarList";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import { DASHBOARD_NAV } from "@/lib/navigation";
import { StatTile } from "@/components/StatTile";
import { getAnalyticsDashboard } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useRequireAuth } from "@/lib/useAuth";
import type { BusinessDashboard } from "@/types";

const FUNNEL_LABEL: Record<string, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  proposal: "Proposal",
  converted: "Converted",
  lost: "Lost",
};

const CONVERSATION_STATUS_LABEL: Record<string, string> = {
  open: "Open",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

const ORDER_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  confirmed: "Confirmed",
  processing: "Processing",
  ready: "Ready",
  delivered: "Delivered",
  cancelled: "Cancelled",
};

// Identity-coded (each row is a genuinely different actor), so unlike the
// other bar lists on this page these get distinct hues + a legend rather
// than one sequential color — matching the inbox's staff/AI/customer
// distinction elsewhere in the app.
const SENDER_LABEL: Record<string, string> = {
  customer: "Customer",
  staff: "Staff",
  ai: "AI Assistant",
  system: "System",
  campaign: "Campaign",
};
// var(--chart-N) — the validated categorical slots from globals.css, in
// their tested order (re-run scripts/validate_palette.js from the dataviz
// skill before reordering or adding a slot). Was flat hex before,
// including zinc-400 for "system" — failed the chroma floor (reads gray,
// not a color) — and amber-500, which failed the dark-mode lightness
// band. See docs/frontend-design-system.md.
const SENDER_COLOR: Record<string, string> = {
  customer: "var(--chart-1)", // blue
  staff: "var(--chart-2)", // emerald — brand accent, matches "staff" bubbles in the inbox
  ai: "var(--chart-3)", // violet
  system: "var(--chart-4)", // cyan — was zinc-400, which failed the chroma-floor check
  campaign: "var(--chart-5)", // amber-600 — was amber-500, which failed the dark lightness band
};

type Preset = "all" | "7d" | "30d" | "month";

const PRESETS: { key: Preset; label: string }[] = [
  { key: "all", label: "All time" },
  { key: "7d", label: "Last 7 days" },
  { key: "30d", label: "Last 30 days" },
  { key: "month", label: "This month" },
];

function presetToRange(preset: Preset): { start?: string; end?: string } {
  const now = new Date();
  switch (preset) {
    case "7d": {
      const start = new Date(now);
      start.setDate(start.getDate() - 7);
      return { start: start.toISOString() };
    }
    case "30d": {
      const start = new Date(now);
      start.setDate(start.getDate() - 30);
      return { start: start.toISOString() };
    }
    case "month": {
      const start = new Date(now.getFullYear(), now.getMonth(), 1);
      return { start: start.toISOString() };
    }
    case "all":
    default:
      return {};
  }
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = seconds / 60;
  if (minutes < 60) return `${minutes.toFixed(1)}m`;
  return `${(minutes / 60).toFixed(1)}h`;
}

function formatMoney(amount: string): string {
  const n = Number(amount);
  return Number.isFinite(n) ? n.toLocaleString(undefined, { minimumFractionDigits: 2 }) : amount;
}

export default function AnalyticsPage() {
  const { user, ready } = useRequireAuth();
  const [preset, setPreset] = useState<Preset>("all");
  const [dashboard, setDashboard] = useState<BusinessDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!ready) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    getAnalyticsDashboard(presetToRange(preset))
      .then((res) => setDashboard(res))
      .catch((err) => setError(getErrorMessage(err, "Failed to load analytics.")))
      .finally(() => setLoading(false));
  }, [ready, preset]);

  if (!ready || !user) {
    return <PageLoading />;
  }

  const funnelItems: BarListItem[] = dashboard
    ? Object.entries(dashboard.funnel).map(([key, value]) => ({
        key,
        label: FUNNEL_LABEL[key] ?? key,
        value,
      }))
    : [];

  const conversationItems: BarListItem[] = dashboard
    ? (["open", "pending", "resolved", "closed"] as const).map((key) => ({
        key,
        label: CONVERSATION_STATUS_LABEL[key],
        value: dashboard.conversations[key],
      }))
    : [];

  const senderKeys = dashboard ? Object.keys(dashboard.messages.by_sender_type) : [];
  const messageItems: BarListItem[] = dashboard
    ? senderKeys.map((key) => ({
        key,
        label: SENDER_LABEL[key] ?? key,
        value: dashboard.messages.by_sender_type[key as keyof typeof dashboard.messages.by_sender_type],
        color: SENDER_COLOR[key],
      }))
    : [];

  const orderStatusItems: BarListItem[] = dashboard
    ? Object.entries(dashboard.orders.by_status).map(([key, value]) => ({
        key,
        label: ORDER_STATUS_LABEL[key] ?? key,
        value,
      }))
    : [];

  const revenueEntries = dashboard ? Object.entries(dashboard.orders.revenue_by_currency) : [];

  return (
    <DashboardShell
      user={user}
      title="Analytics"
      nav={DASHBOARD_NAV}
    >
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}

        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPreset(p.key)}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                preset === p.key
                  ? "border-emerald-600 bg-emerald-50 text-emerald-700 dark:border-emerald-500 dark:bg-emerald-950/40 dark:text-emerald-300"
                  : "border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              }`}
            >
              {p.label}
            </button>
          ))}
          {loading && <span className="self-center text-sm text-zinc-500">Loading…</span>}
        </div>

        <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatTile label="Conversations" value={dashboard ? String(dashboard.conversations.total) : "—"} />
          <StatTile label="Messages" value={dashboard ? String(dashboard.messages.total) : "—"} />
          <StatTile label="AI Replies Sent" value={dashboard ? String(dashboard.ai.ai_replies_sent) : "—"} />
          <StatTile label="Handoffs to Human" value={dashboard ? String(dashboard.ai.handoffs) : "—"} />
          <StatTile
            label="Avg. Response Time"
            value={dashboard ? formatDuration(dashboard.response_time.average_seconds) : "—"}
            hint={
              dashboard
                ? `from ${dashboard.response_time.sample_count} ${dashboard.response_time.sample_count === 1 ? "reply" : "replies"}`
                : undefined
            }
          />
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Customer Funnel
          </h2>
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <BarList items={funnelItems} emptyLabel="No customers yet." />
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Conversations by Status
            </h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <BarList items={conversationItems} emptyLabel="No conversations yet." />
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Messages by Sender
            </h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              {messageItems.length > 0 && (
                <BarListLegend items={messageItems.map((i) => ({ key: i.key, label: i.label, color: i.color! }))} />
              )}
              <BarList items={messageItems} emptyLabel="No messages yet." />
            </div>
          </section>
        </div>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Orders &amp; Revenue
          </h2>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <BarList items={orderStatusItems} emptyLabel="No orders yet." />
            </div>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-3 text-xs text-zinc-500 dark:text-zinc-400">
                Revenue from confirmed-or-later orders, grouped by currency — never summed across
                currencies.
              </p>
              {revenueEntries.length === 0 ? (
                <p className="py-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
                  No revenue yet.
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {revenueEntries.map(([currency, amount]) => (
                    <StatTile key={currency} label={currency} value={formatMoney(amount)} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Top Customer Questions
          </h2>
          <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            Only questions asked more than once — a one-off message isn&apos;t a trend.
          </p>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Question</th>
                  <th className="px-4 py-2 font-medium">Times Asked</th>
                </tr>
              </thead>
              <tbody>
                {dashboard?.top_questions.map((q, i) => (
                  <tr key={i} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{q.text}</td>
                    <td className="px-4 py-2 tabular-nums text-zinc-500 dark:text-zinc-400">{q.count}</td>
                  </tr>
                ))}
                {dashboard && dashboard.top_questions.length === 0 && (
                  <tr>
                    <td colSpan={2} className="px-4 py-6 text-center text-zinc-500">
                      No repeated questions yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </DashboardShell>
  );
}
