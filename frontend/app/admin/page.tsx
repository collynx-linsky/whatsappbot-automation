"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import { ApiError, activateTenant, listTenants, onboardBusiness, suspendTenant } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { Tenant } from "@/types";

const emptyForm = {
  tenant_name: "",
  business_name: "",
  owner_email: "",
  owner_first_name: "",
  owner_last_name: "",
};

export default function AdminPage() {
  const { user, ready } = useRequireAuth();
  const [tenants, setTenants] = useState<Tenant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    try {
      const res = await listTenants();
      setTenants(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tenants.");
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
      setError(err instanceof ApiError ? err.message : "Failed to onboard business.");
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
      setError(err instanceof ApiError ? err.message : "Failed to update tenant.");
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  return (
    <DashboardShell user={user} title="Platform — Super Admin">
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Businesses on the Platform
          </h2>
          <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
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
                      <button
                        onClick={() => handleToggle(t)}
                        className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                      >
                        {t.status === "suspended" ? "Activate" : "Suspend"}
                      </button>
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
