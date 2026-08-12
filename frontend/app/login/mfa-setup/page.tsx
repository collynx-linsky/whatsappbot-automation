"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";

import { Alert } from "@/components/Alert";
import { Field } from "@/components/Field";
import * as api from "@/lib/api";
import { getErrorMessage } from "@/lib/errors";
import {
  clearPendingToken,
  dashboardPathForRole,
  getAccessToken,
  getPendingToken,
  getRefreshToken,
  setSession,
  setTokens,
} from "@/lib/auth";

type Step = "loading" | "scan" | "backup-codes" | "error";

export default function MfaSetupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("loading");
  const [error, setError] = useState<string | null>(null);
  const [secret, setSecret] = useState("");
  const [provisioningUri, setProvisioningUri] = useState("");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [savedCodes, setSavedCodes] = useState(false);

  // Fetch a fresh TOTP secret + QR provisioning URI as soon as we land here.
  // A missing pending token means this page was reached directly (e.g. a
  // stale bookmark, or the 10-minute setup token already expired) — bounce
  // back to /login rather than show a broken form.
  useEffect(() => {
    const token = getPendingToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    api
      .mfaSetup(token)
      .then((data) => {
        setSecret(data.secret);
        setProvisioningUri(data.provisioning_uri);
        setStep("scan");
      })
      .catch((err) => {
        setError(getErrorMessage(err, "Unable to reach the server."));
        setStep("error");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    const token = getPendingToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const data = await api.mfaSetupConfirm(token, code);
      setBackupCodes(data.backup_codes);
      // Real tokens now exist, but we don't have the User object yet (the
      // confirm response only carries access/refresh) — store the tokens so
      // getMe() can authenticate, finish assembling the session once the
      // user has acknowledged their backup codes below.
      setTokens(data.access, data.refresh);
      setStep("backup-codes");
    } catch (err) {
      setError(getErrorMessage(err, "Unable to reach the server."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleContinue() {
    try {
      const user = await api.getMe();
      setSession(getAccessToken() ?? "", getRefreshToken() ?? "", user);
      clearPendingToken();
      router.push(dashboardPathForRole(user.role));
    } catch (err) {
      setError(getErrorMessage(err, "Unable to reach the server."));
    }
  }

  function copyAllCodes() {
    void navigator.clipboard.writeText(backupCodes.join("\n"));
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
            Set up two-factor authentication
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Required for every account on WABA AI — no exceptions.
          </p>
        </div>

        <div className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          {error && <Alert kind="error" message={error} />}

          {step === "loading" && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Preparing your setup…</p>
          )}

          {step === "scan" && (
            <>
              <p className="text-sm text-zinc-600 dark:text-zinc-300">
                Scan this code with an authenticator app (Google Authenticator, Authy, 1Password,
                etc.), then enter the 6-digit code it shows.
              </p>
              <div className="flex justify-center rounded-lg bg-white p-4">
                <QRCodeSVG value={provisioningUri} size={192} />
              </div>
              <details className="text-xs text-zinc-500 dark:text-zinc-400">
                <summary className="cursor-pointer select-none">Can&apos;t scan? Enter manually</summary>
                <code className="mt-1 block break-all rounded bg-zinc-100 p-2 dark:bg-zinc-800">
                  {secret}
                </code>
              </details>
              <form onSubmit={handleConfirm} className="space-y-4">
                <Field label="6-digit code" value={code} onChange={setCode} required />
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Verifying…" : "Confirm and enable"}
                </button>
              </form>
            </>
          )}

          {step === "backup-codes" && (
            <>
              <p className="text-sm text-zinc-600 dark:text-zinc-300">
                Save these backup codes somewhere safe. Each one can be used once to sign in if
                you lose access to your authenticator app. They won&apos;t be shown again.
              </p>
              <div className="grid grid-cols-2 gap-1 rounded-lg bg-zinc-100 p-3 font-mono text-xs text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100">
                {backupCodes.map((c) => (
                  <span key={c}>{c}</span>
                ))}
              </div>
              <button
                type="button"
                onClick={copyAllCodes}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              >
                Copy all codes
              </button>
              <label className="flex items-start gap-2 text-sm text-zinc-600 dark:text-zinc-300">
                <input
                  type="checkbox"
                  checked={savedCodes}
                  onChange={(e) => setSavedCodes(e.target.checked)}
                  className="mt-0.5"
                />
                I&apos;ve saved these codes somewhere safe.
              </label>
              <button
                type="button"
                disabled={!savedCodes}
                onClick={handleContinue}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Continue
              </button>
            </>
          )}

          {step === "error" && (
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              Back to login
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
