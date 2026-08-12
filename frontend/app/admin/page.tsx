"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { BarList, type BarListItem } from "@/components/BarList";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import { Field } from "@/components/Field";
import { Sparkline } from "@/components/Sparkline";
import { StatTile } from "@/components/StatTile";
import {
  activateTenant,
  generateInvoice,
  getPlatformAnalytics,
  listTenants,
  onboardBusiness,
  suspendTenant,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useRequireAuth } from "@/lib/useAuth";
import type { PlatformDashboard, Tenant } from "@/types";

const TENANT_STATUS_LABEL: Record<string, string> = {
  trial: "Trial",
  active: "Active",
  suspended: "Suspended",
  cancelled: "Cancelled",
};

const USER_ROLE_LABEL: Record<string, string> = {
  super_admin: "Super Admin",
  business_owner: "Business Owner",
  manager: "Manager",
  staff: "Staff",
};

const emptyForm = {
  tenant_name: "",
  business_name: "",
  owner_email: "",
  owner_first_name: "",
  owner_last_name: "",
};

export default function AdminPage() {
  const { user, ready } = useRequireAuth({ requireRole: "super_admin" });
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [platform, setPlatform] = useState<PlatformDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  async function refresh() {
    try {
      const [tenantsRes, platformRes] = await Promise.all([listTenants(), getPlatformAnalytics()]);
      setTenants(tenantsRes.results);
      setPlatform(platformRes);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load tenants."));
    }
  }

  useEffect(() => {
    // Data fetch on mount — the resulting setState happens asynchronously
    // once the network response resolves, which is the documented use case
    // for effects (not the synchronous-setState anti-pattern this lint rule
    // otherwise catches).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (ready) refresh();
  }, [ready]);

  async function handleOnboard(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const res = await onboardBusiness(form);
      setSuccess(
        `Created ${res.tenant.name}. Owner ${res.owner.email} temporary password: ${res.temporary_password}`,
      );
      setForm(emptyForm);
      await refresh();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to onboard business."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(tenant: Tenant) {
    setError(null);
    try {
      if (tenant.status === "suspended") {
        await activateTenant(tenant.id);
      } else {
        await suspendTenant(tenant.id);
      }
      await refresh();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to update tenant."));
    }
  }

  // No payment gateway exists to trigger this automatically — a manual
  // per-tenant action, idempotent per (tenant, current calendar month) on
  // the backend, so clicking it twice in the same month is harmless.
  async function handleGenerateInvoice(tenant: Tenant) {
    setError(null);
    setSuccess(null);
    setGeneratingId(tenant.id);
    try {
      const invoice = await generateInvoice({ tenant: tenant.id });
      setSuccess(`Generated ${invoice.invoice_number} (${invoice.currency} ${invoice.amount}).`);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to generate invoice."));
    } finally {
      setGeneratingId(null);
    }
  }

  if (!ready || !user) {
    return <PageLoading />;
  }

  return (
    <DashboardShell user={user} title="Platform — Super Admin">
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Platform Analytics
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Tenants" value={platform ? String(platform.tenants.total) : "—"} />
            <StatTile label="Businesses" value={platform ? String(platform.businesses.total) : "—"} />
            <StatTile label="Conversations" value={platform ? String(platform.conversations.total) : "—"} />
            <StatTile label="Messages" value={platform ? String(platform.messages.total) : "—"} />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Tenants by Status
              </h3>
              <BarList
                items={
                  platform
                    ? (["trial", "active", "suspended", "cancelled"] as const).map((key) => ({
                        key,
                        label: TENANT_STATUS_LABEL[key],
                        value: platform.tenants[key],
                      }))
                    : []
                }
              />
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Users by Role
              </h3>
              <BarList
                items={
                  platform
                    ? (["super_admin", "business_owner", "manager", "staff"] as const).map(
                        (key): BarListItem => ({
                          key,
                          label: USER_ROLE_LABEL[key],
                          value: platform.users[key],
                        }),
                      )
                    : []
                }
              />
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                New Tenants (30 days)
              </h3>
              {platform ? <Sparkline data={platform.signup_trend} /> : <p className="text-sm text-zinc-500">—</p>}
              {platform && Object.keys(platform.orders.revenue_by_currency).length > 0 && (
                <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                    Platform Revenue
                  </p>
                  <dl className="space-y-1 text-sm">
                    {Object.entries(platform.orders.revenue_by_currency).map(([currency, amount]) => (
                      <div key={currency} className="flex justify-between">
                        <dt className="text-zinc-500 dark:text-zinc-400">{currency}</dt>
                        <dd className="tabular-nums text-zinc-900 dark:text-zinc-100">{amount}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Businesses on the Platform
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Tenant</th>
                  <th className="px-4 py-2 font-medium">Plan</th>
                  <th className="px-4 py-2 font-medium">Businesses</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {tenants?.map((t) => (
                  <tr key={t.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{t.name}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{t.plan_name ?? "—"}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{t.business_count}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          t.status === "suspended"
                            ? "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300"
                            : "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                        }`}
                      >
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleToggle(t)}
                          className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                        >
                          {t.status === "suspended" ? "Activate" : "Suspend"}
                        </button>
                        <button
                          onClick={() => handleGenerateInvoice(t)}
                          disabled={generatingId === t.id || !t.plan}
                          title={!t.plan ? "No plan assigned — cannot generate an invoice." : undefined}
                          className="text-sm font-medium text-zinc-600 hover:underline disabled:cursor-not-allowed disabled:opacity-50 dark:text-zinc-400"
                        >
                          {generatingId === t.id ? "Generating…" : "Generate Invoice"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {tenants?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No businesses yet — onboard one below.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Onboard a New Business
          </h2>
          <form
            onSubmit={handleOnboard}
            className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <Field label="Tenant / Company name" value={form.tenant_name}
              onChange={(v) => setForm({ ...form, tenant_name: v })} required />
            <Field label="Business name" value={form.business_name}
              onChange={(v) => setForm({ ...form, business_name: v })} required />
            <Field label="Owner email" type="email" value={form.owner_email}
              onChange={(v) => setForm({ ...form, owner_email: v })} required />
            <Field label="Owner first name" value={form.owner_first_name}
              onChange={(v) => setForm({ ...form, owner_first_name: v })} required />
            <Field label="Owner last name" value={form.owner_last_name}
              onChange={(v) => setForm({ ...form, owner_last_name: v })} />

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Creating…" : "Create Business"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </DashboardShell>
  );
}
