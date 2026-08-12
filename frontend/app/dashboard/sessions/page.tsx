"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import { listSessions, revokeSession } from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useRequireAuth } from "@/lib/useAuth";
import type { Session } from "@/types";

export default function SessionsPage() {
  const { user, ready } = useRequireAuth();
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revokingJti, setRevokingJti] = useState<string | null>(null);

  async function refresh() {
    try {
      const res = await listSessions();
      setSessions(res);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load sessions."));
    }
  }

  useEffect(() => {
    if (!ready) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [ready]);

  async function handleRevoke(jti: string) {
    setError(null);
    setRevokingJti(jti);
    try {
      await revokeSession(jti);
      await refresh();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to revoke session."));
    } finally {
      setRevokingJti(null);
    }
  }

  if (!ready || !user) {
    return <PageLoading />;
  }

  return (
    <DashboardShell user={user} title="Active Sessions">
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Signed-in sessions
          </h2>
          <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">
            Every device or browser currently signed in to your account. Revoking a session signs
            it out immediately — do this if you don&apos;t recognize one.
          </p>

          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Signed in</th>
                  <th className="px-4 py-2 font-medium">Expires</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions?.map((s) => (
                  <tr key={s.jti} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                    <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">
                      {new Date(s.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                      {new Date(s.expires_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleRevoke(s.jti)}
                        disabled={revokingJti === s.jti}
                        className="text-sm font-medium text-red-600 hover:underline disabled:cursor-not-allowed disabled:opacity-60 dark:text-red-400"
                      >
                        {revokingJti === s.jti ? "Revoking…" : "Revoke"}
                      </button>
                    </td>
                  </tr>
                ))}
                {sessions === null && !error && (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-zinc-500">
                      Loading…
                    </td>
                  </tr>
                )}
                {sessions?.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-6 text-center text-zinc-500">
                      No active sessions.
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
