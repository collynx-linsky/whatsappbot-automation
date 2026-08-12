"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import { EmptyState } from "@/components/EmptyState";
import { DASHBOARD_NAV } from "@/lib/navigation";
import { Field } from "@/components/Field";
import {
  createWhatsAppAccount,
  listBusinesses,
  listWhatsAppAccounts,
  updateWhatsAppAccount,
} from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import { useRequireAuth } from "@/lib/useAuth";
import type { WhatsAppAccount, WhatsAppAccountStatus } from "@/types";
import { IconPhone } from "@/components/Icons";

const STATUS_STYLE: Record<WhatsAppAccountStatus, string> = {
  pending: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  connected: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  disconnected: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  error: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

const emptyConnectForm = {
  display_name: "",
  phone_number: "",
  phone_number_id: "",
  business_account_id: "",
  access_token: "",
};

export default function WhatsAppPage() {
  const { user, ready } = useRequireAuth();
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<WhatsAppAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [connectForm, setConnectForm] = useState(emptyConnectForm);
  const [connecting, setConnecting] = useState(false);

  const [reconnectingId, setReconnectingId] = useState<string | null>(null);
  const [reconnectToken, setReconnectToken] = useState("");
  const [reconnecting, setReconnecting] = useState(false);

  const canManage = user?.role === "business_owner" || user?.role === "manager";

  async function refreshAccounts() {
    try {
      const res = await listWhatsAppAccounts();
      setAccounts(res.results);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load WhatsApp accounts."));
    }
  }

  useEffect(() => {
    if (!ready || !canManage) return;
    listBusinesses()
      .then((res) => setBusinessId(res.results[0]?.id ?? null))
      .catch(() => {
        /* the connect form just stays disabled without a business id */
      });
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAccounts();
  }, [ready, canManage]);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!businessId) return;
    setError(null);
    setSuccess(null);
    setConnecting(true);
    try {
      await createWhatsAppAccount({ business: businessId, ...connectForm });
      setSuccess(`Connected ${connectForm.phone_number}.`);
      setConnectForm(emptyConnectForm);
      await refreshAccounts();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to connect WhatsApp account."));
    } finally {
      setConnecting(false);
    }
  }

  async function handleReconnect(account: WhatsAppAccount) {
    if (!reconnectToken.trim()) return;
    setError(null);
    setSuccess(null);
    setReconnecting(true);
    try {
      await updateWhatsAppAccount(account.id, { access_token: reconnectToken });
      setSuccess(`Reconnected ${account.phone_number} with a new access token.`);
      setReconnectingId(null);
      setReconnectToken("");
      await refreshAccounts();
    } catch (err) {
      setError(getErrorMessage(err, "Failed to reconnect."));
    } finally {
      setReconnecting(false);
    }
  }

  if (!ready || !user) {
    return <PageLoading />;
  }

  return (
    <DashboardShell
      user={user}
      title="WhatsApp"
      nav={DASHBOARD_NAV}
    >
      {!canManage ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-white/50 p-5 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-400">
          Connecting a WhatsApp number is only available to business owners and managers.
        </p>
      ) : (
        <div className="space-y-8">
          {error && <Alert kind="error" message={error} />}
          {success && <Alert kind="success" message={success} />}

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Connected Numbers
            </h2>
            <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
              The access token is never shown again after it&apos;s saved — it&apos;s encrypted at
              rest and this API never returns it, by design.
            </p>
            <div className="space-y-3">
              {accounts?.map((a) => (
                <div
                  key={a.id}
                  className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium text-zinc-900 dark:text-zinc-100">
                        {a.display_name || a.phone_number}
                      </p>
                      <p className="text-sm text-zinc-500 dark:text-zinc-400">{a.phone_number}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[a.status]}`}
                      >
                        {a.status}
                      </span>
                      <button
                        onClick={() =>
                          reconnectingId === a.id ? setReconnectingId(null) : setReconnectingId(a.id)
                        }
                        className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                      >
                        {reconnectingId === a.id ? "Cancel" : "Reconnect"}
                      </button>
                    </div>
                  </div>
                  {a.status === "error" && a.last_error && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">{a.last_error}</p>
                  )}
                  {a.connected_at && (
                    <p className="mt-2 text-xs text-zinc-400">
                      Connected {new Date(a.connected_at).toLocaleString()}
                    </p>
                  )}
                  {reconnectingId === a.id && (
                    <div className="mt-3 flex flex-col gap-2 border-t border-zinc-100 pt-3 sm:flex-row dark:border-zinc-800">
                      <input
                        type="password"
                        placeholder="New access token"
                        value={reconnectToken}
                        onChange={(e) => setReconnectToken(e.target.value)}
                        className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                      />
                      <button
                        onClick={() => handleReconnect(a)}
                        disabled={reconnecting || !reconnectToken.trim()}
                        className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {reconnecting ? "Saving…" : "Save"}
                      </button>
                    </div>
                  )}
                </div>
              ))}
              {accounts?.length === 0 && (
                <div className="rounded-xl border border-dashed border-zinc-300 bg-white/50 dark:border-zinc-700 dark:bg-zinc-900/50">
                  <EmptyState
                    icon={<IconPhone className="h-8 w-8" />}
                    title="No WhatsApp number connected"
                    description="Connect a WhatsApp Business number below to start sending and receiving real messages."
                  />
                </div>
              )}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Connect a Number
            </h2>
            <form
              onSubmit={handleConnect}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Display name (optional)"
                value={connectForm.display_name}
                onChange={(v) => setConnectForm({ ...connectForm, display_name: v })}
              />
              <Field
                label="Phone number (E.164, e.g. +254712345678)"
                value={connectForm.phone_number}
                onChange={(v) => setConnectForm({ ...connectForm, phone_number: v })}
                required
              />
              <Field
                label="Phone number ID (from Meta)"
                value={connectForm.phone_number_id}
                onChange={(v) => setConnectForm({ ...connectForm, phone_number_id: v })}
                required
              />
              <Field
                label="WhatsApp Business Account ID"
                value={connectForm.business_account_id}
                onChange={(v) => setConnectForm({ ...connectForm, business_account_id: v })}
                required
              />
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Access token
                </label>
                <input
                  type="password"
                  required
                  value={connectForm.access_token}
                  onChange={(e) => setConnectForm({ ...connectForm, access_token: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                />
              </div>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={connecting || !businessId}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {connecting ? "Connecting…" : "Connect"}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </DashboardShell>
  );
}
