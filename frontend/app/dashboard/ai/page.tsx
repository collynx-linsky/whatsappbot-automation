"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import { ApiError, getAISettings, testAI, updateAISettings } from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { AISettings, AITestResult } from "@/types";

const selectClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";
const textareaClass = selectClass + " resize-y";
const labelClass = "block text-sm font-medium text-zinc-700 dark:text-zinc-300";

type FormState = {
  assistant_name: string;
  language: string;
  tone: AISettings["tone"];
  welcome_message: string;
  fallback_message: string;
  max_response_length: string;
  mode: AISettings["mode"];
  ai_enabled: boolean;
  human_handoff_enabled: boolean;
  confidence_threshold: string;
  handoff_keywords: string; // comma-separated in the UI, split into an array on save
  provider: AISettings["provider"];
  model_name: string;
  system_prompt: string;
};

function toForm(s: AISettings): FormState {
  return {
    assistant_name: s.assistant_name,
    language: s.language,
    tone: s.tone,
    welcome_message: s.welcome_message,
    fallback_message: s.fallback_message,
    max_response_length: String(s.max_response_length),
    mode: s.mode,
    ai_enabled: s.ai_enabled,
    human_handoff_enabled: s.human_handoff_enabled,
    confidence_threshold: String(s.confidence_threshold),
    handoff_keywords: s.handoff_keywords.join(", "),
    provider: s.provider,
    model_name: s.model_name,
    system_prompt: s.system_prompt,
  };
}

export default function AISettingsPage() {
  const { user, ready } = useRequireAuth();
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [testMessage, setTestMessage] = useState("");
  const [testResult, setTestResult] = useState<AITestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const canManage = user?.role === "business_owner" || user?.role === "manager";

  useEffect(() => {
    if (!ready || !canManage) return;
    getAISettings()
      .then((res) => setForm(toForm(res)))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load AI settings."));
  }, [ready, canManage]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const updated = await updateAISettings({
        assistant_name: form.assistant_name,
        language: form.language,
        tone: form.tone,
        welcome_message: form.welcome_message,
        fallback_message: form.fallback_message,
        max_response_length: Number(form.max_response_length) || 500,
        mode: form.mode,
        ai_enabled: form.ai_enabled,
        human_handoff_enabled: form.human_handoff_enabled,
        confidence_threshold: Number(form.confidence_threshold),
        handoff_keywords: form.handoff_keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
        provider: form.provider,
        model_name: form.model_name,
        system_prompt: form.system_prompt,
      });
      setForm(toForm(updated));
      setSuccess("AI settings saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save AI settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(e: React.FormEvent) {
    e.preventDefault();
    setTestError(null);
    setTestResult(null);
    setTesting(true);
    try {
      const res = await testAI(testMessage);
      setTestResult(res);
    } catch (err) {
      setTestError(err instanceof ApiError ? err.message : "Failed to test the assistant.");
    } finally {
      setTesting(false);
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  return (
    <DashboardShell
      user={user}
      title="AI Assistant"
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
      {!canManage ? (
        <p className="rounded-xl border border-dashed border-zinc-300 bg-white/50 p-5 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/50 dark:text-zinc-400">
          AI assistant configuration is only available to business owners and managers.
        </p>
      ) : (
        <div className="space-y-8">
          {error && <Alert kind="error" message={error} />}
          {success && <Alert kind="success" message={success} />}

          {!form ? (
            <p className="text-sm text-zinc-500">Loading…</p>
          ) : (
            <form onSubmit={handleSave} className="space-y-8">
              <section>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Identity
                </h2>
                <div className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900">
                  <Field
                    label="Assistant name"
                    value={form.assistant_name}
                    onChange={(v) => setForm({ ...form, assistant_name: v })}
                    required
                  />
                  <Field
                    label="Language (ISO code)"
                    value={form.language}
                    onChange={(v) => setForm({ ...form, language: v })}
                  />
                  <div>
                    <label className={labelClass}>Tone</label>
                    <select
                      value={form.tone}
                      onChange={(e) => setForm({ ...form, tone: e.target.value as FormState["tone"] })}
                      className={selectClass}
                    >
                      <option value="friendly">Friendly</option>
                      <option value="professional">Professional</option>
                      <option value="casual">Casual</option>
                      <option value="formal">Formal</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2">
                    <label className={labelClass}>Welcome message</label>
                    <textarea
                      rows={2}
                      value={form.welcome_message}
                      onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
                      className={textareaClass}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className={labelClass}>Fallback message (shown on handoff)</label>
                    <textarea
                      rows={2}
                      value={form.fallback_message}
                      onChange={(e) => setForm({ ...form, fallback_message: e.target.value })}
                      className={textareaClass}
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className={labelClass}>
                      System prompt <span className="font-normal text-zinc-400">(optional — a default is built from your business profile if left blank)</span>
                    </label>
                    <textarea
                      rows={4}
                      value={form.system_prompt}
                      onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                      className={textareaClass}
                    />
                  </div>
                </div>
              </section>

              <section>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Behavior
                </h2>
                <div className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900">
                  <div>
                    <label className={labelClass}>Mode</label>
                    <select
                      value={form.mode}
                      onChange={(e) => setForm({ ...form, mode: e.target.value as FormState["mode"] })}
                      className={selectClass}
                    >
                      <option value="hybrid">Hybrid (AI with handoff)</option>
                      <option value="ai">AI-only</option>
                      <option value="human">Human-only</option>
                    </select>
                  </div>
                  <Field
                    label="Max response length (characters)"
                    type="number"
                    value={form.max_response_length}
                    onChange={(v) => setForm({ ...form, max_response_length: v })}
                  />
                  <div className="flex items-center gap-2 pt-6">
                    <input
                      id="ai_enabled"
                      type="checkbox"
                      checked={form.ai_enabled}
                      onChange={(e) => setForm({ ...form, ai_enabled: e.target.checked })}
                      className="h-4 w-4 rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <label htmlFor="ai_enabled" className="text-sm text-zinc-700 dark:text-zinc-300">
                      AI enabled
                    </label>
                  </div>
                  <div className="flex items-center gap-2 pt-6">
                    <input
                      id="handoff_enabled"
                      type="checkbox"
                      checked={form.human_handoff_enabled}
                      onChange={(e) => setForm({ ...form, human_handoff_enabled: e.target.checked })}
                      className="h-4 w-4 rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <label htmlFor="handoff_enabled" className="text-sm text-zinc-700 dark:text-zinc-300">
                      Human handoff enabled
                    </label>
                  </div>
                  <Field
                    label="Confidence threshold (0–1)"
                    type="number"
                    value={form.confidence_threshold}
                    onChange={(v) => setForm({ ...form, confidence_threshold: v })}
                  />
                  <div className="sm:col-span-2">
                    <label className={labelClass}>
                      Handoff keywords{" "}
                      <span className="font-normal text-zinc-400">
                        (comma-separated — any match in a customer message forces handoff)
                      </span>
                    </label>
                    <textarea
                      rows={2}
                      value={form.handoff_keywords}
                      onChange={(e) => setForm({ ...form, handoff_keywords: e.target.value })}
                      className={textareaClass}
                    />
                  </div>
                </div>
              </section>

              <section>
                <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Provider
                </h2>
                <div className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900">
                  <div>
                    <label className={labelClass}>Provider</label>
                    <select
                      value={form.provider}
                      onChange={(e) => setForm({ ...form, provider: e.target.value as FormState["provider"] })}
                      className={selectClass}
                    >
                      <option value="openai">OpenAI</option>
                      <option value="anthropic">Anthropic</option>
                    </select>
                  </div>
                  <Field
                    label="Model (optional — provider default if blank)"
                    value={form.model_name}
                    onChange={(v) => setForm({ ...form, model_name: v })}
                  />
                </div>
              </section>

              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save Settings"}
              </button>
            </form>
          )}

          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Test Your Assistant
            </h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-3 text-xs text-zinc-500 dark:text-zinc-400">
                Runs the same handoff-check and reply logic as a real customer message — nothing here
                touches your real conversations.
              </p>
              <form onSubmit={handleTest} className="flex flex-col gap-3 sm:flex-row">
                <input
                  type="text"
                  required
                  placeholder="Type a message a customer might send…"
                  value={testMessage}
                  onChange={(e) => setTestMessage(e.target.value)}
                  className={selectClass + " flex-1"}
                />
                <button
                  type="submit"
                  disabled={testing}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                >
                  {testing ? "Testing…" : "Test"}
                </button>
              </form>

              {testError && (
                <div className="mt-3">
                  <Alert kind="error" message={testError} />
                </div>
              )}

              {testResult && (
                <div
                  className={`mt-3 rounded-lg border p-3 text-sm ${
                    testResult.handed_off
                      ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300"
                      : "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300"
                  }`}
                >
                  {testResult.handed_off ? (
                    <p>
                      <strong>Handed off to a human.</strong> Reason: {testResult.reason}
                    </p>
                  ) : (
                    <>
                      <p className="whitespace-pre-wrap">{testResult.reply}</p>
                      {testResult.confidence != null && (
                        <p className="mt-2 text-xs opacity-80">
                          Confidence: {(testResult.confidence * 100).toFixed(0)}%
                        </p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </DashboardShell>
  );
}
