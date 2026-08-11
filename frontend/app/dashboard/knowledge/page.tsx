"use client";

import { Fragment, useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import {
  ApiError,
  createKnowledgeDocument,
  deleteKnowledgeDocument,
  listBusinesses,
  listKnowledgeChunks,
  listKnowledgeDocuments,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type { KnowledgeChunk, KnowledgeDocument, KnowledgeSourceType } from "@/types";

// Any document still processing gets picked up on the next tick — no
// real-time channel exists on this backend, same reasoning as the inbox's
// polling (see docs/rag.md / ROADMAP's inbox entry).
const POLL_MS = 5000;

const STATUS_STYLE: Record<KnowledgeDocument["status"], string> = {
  pending: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  processing: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  ready: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

const selectClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";

const emptyForm = { title: "", source_type: "text" as KnowledgeSourceType, raw_text: "" };

export default function KnowledgePage() {
  const { user, ready } = useRequireAuth();
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunk[] | null>(null);
  const [chunksLoading, setChunksLoading] = useState(false);

  const canManage = user?.role === "business_owner" || user?.role === "manager";

  async function refreshDocuments() {
    try {
      const res = await listKnowledgeDocuments();
      setDocuments(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load knowledge base.");
    }
  }

  useEffect(() => {
    if (!ready) return;
    listBusinesses()
      .then((res) => setBusinessId(res.results[0]?.id ?? null))
      .catch(() => {
        /* the upload form just stays disabled without a business id */
      });
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshDocuments();
    const interval = setInterval(refreshDocuments, POLL_MS);
    return () => clearInterval(interval);
  }, [ready]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!businessId) return;
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      await createKnowledgeDocument({
        business: businessId,
        title: form.title,
        source_type: form.source_type,
        file: form.source_type === "upload" ? (file ?? undefined) : undefined,
        raw_text: form.source_type === "text" ? form.raw_text : undefined,
      });
      setSuccess(`"${form.title}" uploaded — processing now.`);
      setForm(emptyForm);
      setFile(null);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to upload document.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(doc: KnowledgeDocument) {
    setError(null);
    try {
      await deleteKnowledgeDocument(doc.id);
      if (expandedId === doc.id) setExpandedId(null);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete document.");
    }
  }

  async function handleToggleChunks(doc: KnowledgeDocument) {
    if (expandedId === doc.id) {
      setExpandedId(null);
      setChunks(null);
      return;
    }
    setExpandedId(doc.id);
    setChunks(null);
    setChunksLoading(true);
    try {
      const res = await listKnowledgeChunks(doc.id);
      setChunks(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load chunks.");
    } finally {
      setChunksLoading(false);
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  return (
    <DashboardShell
      user={user}
      title="Knowledge Base"
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
      <div className="space-y-8">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Documents here ground the AI assistant&apos;s replies — see the{" "}
          <a href="/dashboard/ai" className="text-emerald-600 hover:underline dark:text-emerald-400">
            AI Assistant
          </a>{" "}
          page for how strictly it&apos;s told to stick to what&apos;s uploaded here.
        </p>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Documents
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Title</th>
                  <th className="px-4 py-2 font-medium">Source</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Chunks</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents?.map((doc) => (
                  <Fragment key={doc.id}>
                    <tr className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{doc.title}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {doc.source_type === "upload" ? "File" : "Pasted text"}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[doc.status]}`}
                          title={doc.status === "failed" ? doc.error_message : undefined}
                        >
                          {doc.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {doc.chunk_count === 0
                          ? "—"
                          : doc.embedded_chunk_count < doc.chunk_count
                            ? `${doc.chunk_count} (${doc.embedded_chunk_count} embedded — keyword fallback for the rest)`
                            : `${doc.chunk_count} embedded`}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-3">
                          <button
                            onClick={() => handleToggleChunks(doc)}
                            className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                          >
                            {expandedId === doc.id ? "Hide chunks" : "View chunks"}
                          </button>
                          {canManage && (
                            <button
                              onClick={() => handleDelete(doc)}
                              className="text-sm font-medium text-red-600 hover:underline dark:text-red-400"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {expandedId === doc.id && (
                      <tr className="border-b border-zinc-100 bg-zinc-50 last:border-0 dark:border-zinc-800 dark:bg-zinc-900/40">
                        <td colSpan={5} className="px-4 py-3">
                          {doc.status === "failed" && doc.error_message && (
                            <p className="mb-2 text-sm text-red-600 dark:text-red-400">
                              {doc.error_message}
                            </p>
                          )}
                          {chunksLoading && <p className="text-sm text-zinc-500">Loading chunks…</p>}
                          {!chunksLoading && chunks?.length === 0 && (
                            <p className="text-sm text-zinc-500">
                              No chunks yet{doc.status !== "ready" ? " — still processing." : "."}
                            </p>
                          )}
                          {!chunksLoading && chunks && chunks.length > 0 && (
                            <ul className="space-y-2">
                              {chunks.map((c) => (
                                <li
                                  key={c.id}
                                  className="rounded-lg border border-zinc-200 bg-white p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950"
                                >
                                  <div className="mb-1 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
                                    <span>Chunk {c.chunk_index + 1}</span>
                                    <span>{c.is_embedded ? "Embedded" : "Keyword-only"}</span>
                                  </div>
                                  <p className="whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">
                                    {c.content}
                                  </p>
                                </li>
                              ))}
                            </ul>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {documents?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No documents yet — upload one below.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {canManage && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              Add a Document
            </h2>
            <form
              onSubmit={handleUpload}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Title"
                value={form.title}
                onChange={(v) => setForm({ ...form, title: v })}
                required
              />
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Source
                </label>
                <select
                  value={form.source_type}
                  onChange={(e) =>
                    setForm({ ...form, source_type: e.target.value as KnowledgeSourceType })
                  }
                  className={selectClass}
                >
                  <option value="text">Paste text</option>
                  <option value="upload">Upload a file (.txt or .pdf)</option>
                </select>
              </div>

              {form.source_type === "text" ? (
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Content
                  </label>
                  <textarea
                    required
                    rows={6}
                    value={form.raw_text}
                    onChange={(e) => setForm({ ...form, raw_text: e.target.value })}
                    className={selectClass + " resize-y"}
                  />
                </div>
              ) : (
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    File
                  </label>
                  <input
                    type="file"
                    required
                    accept=".txt,.pdf"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="mt-1 block w-full text-sm text-zinc-700 file:mr-3 file:rounded-lg file:border-0 file:bg-emerald-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-emerald-700 dark:text-zinc-300"
                  />
                </div>
              )}

              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submitting || !businessId}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Uploading…" : "Add Document"}
                </button>
              </div>
            </form>
          </section>
        )}
      </div>
    </DashboardShell>
  );
}
