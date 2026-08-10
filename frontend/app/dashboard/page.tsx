"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { ApiError, listBusinesses } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { Business } from "@/types";

export default function DashboardPage() {
  const { user, ready } = useRequireAuth();
  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    listBusinesses()
      .then((res) => setBusinesses(res.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load business."));
  }, [ready]);

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  return (
    <DashboardShell user={user} title="Business Dashboard">
      <div className="space-y-6">
        {error && <Alert kind="error" message={error} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Your Business
          </h2>

          {businesses === null && !error && (
            <p className="text-sm text-zinc-500">Loading…</p>
          )}

          {businesses?.length === 0 && (
            <p className="text-sm text-zinc-500">
              No business is associated with your account yet.
            </p>
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

        <section className="rounded-xl border border-dashed border-zinc-300 bg-white/50 p-5 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-400">
          The WhatsApp inbox, customers, products, orders, AI assistant, and knowledge base
          modules land in the next build phases — see docs/ROADMAP.md.
        </section>
      </div>
    </DashboardShell>
  );
}
