"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Alert } from "@/components/Alert";
import { Field } from "@/components/Field";
import * as api from "@/lib/api";
import { ApiError } from "@/lib/api";
import {
  clearPendingToken,
  dashboardPathForRole,
  getPendingToken,
  setSession,
  setTokens,
} from "@/lib/auth";

export default function MfaVerifyPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [backupCode, setBackupCode] = useState("");
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const token = getPendingToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const data = useBackupCode
        ? await api.mfaVerify(token, { backup_code: backupCode })
        : await api.mfaVerify(token, { code });
      setTokens(data.access, data.refresh);
      const user = await api.getMe();
      setSession(data.access, data.refresh, user);
      clearPendingToken();
      router.push(dashboardPathForRole(user.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Two-factor verification
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            {useBackupCode
              ? "Enter one of your saved backup codes."
              : "Enter the 6-digit code from your authenticator app."}
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          {error && <Alert kind="error" message={error} />}

          {useBackupCode ? (
            <Field label="Backup code" value={backupCode} onChange={setBackupCode} required />
          ) : (
            <Field label="6-digit code" value={code} onChange={setCode} required />
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Verifying…" : "Verify"}
          </button>

          <button
            type="button"
            onClick={() => {
              setUseBackupCode((v) => !v);
              setError(null);
            }}
            className="w-full text-center text-xs text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            {useBackupCode ? "Use my authenticator app instead" : "Use a backup code instead"}
          </button>
        </form>
      </div>
    </div>
  );
}
