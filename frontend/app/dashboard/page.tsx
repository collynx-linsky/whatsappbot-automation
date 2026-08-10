"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import { ApiError, createStaff, listBusinesses, listStaff, updateStaff } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { Business, StaffMember } from "@/types";

const emptyStaffForm = { email: "", first_name: "", last_name: "", role: "staff" as "manager" | "staff" };

export default function DashboardPage() {
  const { user, ready } = useRequireAuth();
  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [staffForm, setStaffForm] = useState(emptyStaffForm);
  const [submitting, setSubmitting] = useState(false);

  async function refreshStaff() {
    try {
      const res = await listStaff();
      setStaff(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load team.");
    }
  }

  useEffect(() => {
    if (!ready) return;
    // Data fetch on mount — setState happens asynchronously once the
    // network response resolves (the documented effect use case, not the
    // synchronous-setState anti-pattern react-hooks/set-state-in-effect
    // otherwise catches).
    listBusinesses()
      .then((res) => setBusinesses(res.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load business."));
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshStaff();
  }, [ready]);

  async function handleAddStaff(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const res = await createStaff(staffForm);
      setSuccess(
        `Added ${res.user.full_name} (${res.user.role}). Temporary password: ${res.temporary_password}`,
      );
      setStaffForm(emptyStaffForm);
      await refreshStaff();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add team member.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(member: StaffMember) {
    setError(null);
    try {
      await updateStaff(member.id, { is_active: !member.is_active });
      await refreshStaff();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update team member.");
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  const isOwner = user.role === "business_owner";

  return (
    <DashboardShell
      user={user}
      title="Business Dashboard"
      nav={[
        { label: "Overview", href: "/dashboard" },
        { label: "Products & Orders", href: "/dashboard/products" },
      ]}
    >
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Your Business
          </h2>

          {businesses === null && !error && <p className="text-sm text-zinc-500">Loading…</p>}
          {businesses?.length === 0 && (
            <p className="text-sm text-zinc-500">No business is associated with your account yet.</p>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {businesses?.map((b) => (
              <div
                key={b.id}
                className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
              >
                <h3 className="font-semibold text-zinc-900 dark:text-zinc-50">{b.name}</h3>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                  {b.category.replace("_", " ")} · {b.country}
                </p>
                <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  <dt className="text-zinc-500 dark:text-zinc-400">Currency</dt>
                  <dd className="text-zinc-900 dark:text-zinc-100">{b.currency}</dd>
                  <dt className="text-zinc-500 dark:text-zinc-400">Status</dt>
                  <dd className="text-zinc-900 dark:text-zinc-100">
                    {b.is_active ? "Active" : "Inactive"}
                  </dd>
                </dl>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Team
          </h2>
          <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Email</th>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  {isOwner && <th className="px-4 py-2 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {staff?.map((m) => (
                  <tr key={m.id} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{m.full_name}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{m.email}</td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                      {m.role.replace("_", " ")}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          m.is_active
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                            : "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300"
                        }`}
                      >
                        {m.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    {isOwner && (
                      <td className="px-4 py-2">
                        {m.role !== "business_owner" && m.id !== user.id && (
                          <button
                            onClick={() => handleToggleActive(m)}
                            className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                          >
                            {m.is_active ? "Deactivate" : "Activate"}
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
                {staff?.length === 0 && (
                  <tr>
                    <td colSpan={isOwner ? 5 : 4} className="px-4 py-6 text-center text-zinc-500">
                      No team members yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {isOwner && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Add a Team Member
            </h2>
            <form
              onSubmit={handleAddStaff}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Email"
                type="email"
                value={staffForm.email}
                onChange={(v) => setStaffForm({ ...staffForm, email: v })}
                required
              />
              <Field
                label="First name"
                value={staffForm.first_name}
                onChange={(v) => setStaffForm({ ...staffForm, first_name: v })}
                required
              />
              <Field
                label="Last name"
                value={staffForm.last_name}
                onChange={(v) => setStaffForm({ ...staffForm, last_name: v })}
              />
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Role
                </label>
                <select
                  value={staffForm.role}
                  onChange={(e) =>
                    setStaffForm({ ...staffForm, role: e.target.value as "manager" | "staff" })
                  }
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                >
                  <option value="staff">Staff</option>
                  <option value="manager">Manager</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Adding…" : "Add Team Member"}
                </button>
              </div>
            </form>
          </section>
        )}

        <section className="rounded-xl border border-dashed border-zinc-300 bg-white/50 p-5 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-400">
          The WhatsApp inbox, customers, products, orders, AI assistant, and knowledge base
          modules land in the next build phases — see docs/ROADMAP.md.
        </section>
      </div>
    </DashboardShell>
  );
}
