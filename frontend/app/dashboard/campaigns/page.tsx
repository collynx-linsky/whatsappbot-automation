"use client";

import { Fragment, useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { DashboardShell } from "@/components/DashboardShell";
import { Field } from "@/components/Field";
import {
  ApiError,
  createCampaign,
  createSegment,
  createTemplate,
  deleteSegment,
  listBusinesses,
  listCampaignRecipients,
  listCampaigns,
  listSegments,
  listTemplates,
  previewSegment,
  sendCampaign,
  updateTemplate,
} from "@/lib/api";
import { useRequireAuth } from "@/lib/useAuth";
import type {
  Campaign,
  CampaignRecipient,
  CustomerSource,
  LeadStatus,
  MessageTemplate,
  Segment,
  SegmentPreview,
  TemplateStatus,
} from "@/types";

// Campaigns send async via Celery, same reasoning as the knowledge base's
// processing poll — no real-time channel on this backend.
const POLL_MS = 5000;

const selectClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100";
const labelClass = "block text-sm font-medium text-zinc-700 dark:text-zinc-300";

const TEMPLATE_STATUS_STYLE: Record<TemplateStatus, string> = {
  draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  pending_approval: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  approved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  rejected: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

const CAMPAIGN_STATUS_STYLE: Record<Campaign["status"], string> = {
  draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  scheduled: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  sending: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  sent: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
  cancelled: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

const LEAD_STATUSES: LeadStatus[] = ["new", "contacted", "qualified", "proposal", "converted", "lost"];
const CUSTOMER_SOURCES: CustomerSource[] = [
  "whatsapp",
  "website",
  "referral",
  "walk_in",
  "campaign",
  "other",
];

const emptyTemplateForm = {
  name: "",
  whatsapp_template_name: "",
  category: "marketing" as MessageTemplate["category"],
  language_code: "en_US",
  body_text: "",
};

const emptySegmentForm = { name: "", description: "", statuses: [] as LeadStatus[], sources: [] as CustomerSource[], tags: "" };

const emptyCampaignForm = { name: "", segment: "", template: "", template_variables: "", scheduled_at: "" };

export default function CampaignsPage() {
  const { user, ready } = useRequireAuth();
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<MessageTemplate[] | null>(null);
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [templateForm, setTemplateForm] = useState(emptyTemplateForm);
  const [submittingTemplate, setSubmittingTemplate] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [templateEdit, setTemplateEdit] = useState({
    status: "draft" as TemplateStatus,
    whatsapp_template_name: "",
    rejection_reason: "",
  });

  const [segmentForm, setSegmentForm] = useState(emptySegmentForm);
  const [submittingSegment, setSubmittingSegment] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [preview, setPreview] = useState<SegmentPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [campaignForm, setCampaignForm] = useState(emptyCampaignForm);
  const [submittingCampaign, setSubmittingCampaign] = useState(false);
  const [sendingId, setSendingId] = useState<string | null>(null);
  const [expandedCampaignId, setExpandedCampaignId] = useState<string | null>(null);
  const [recipients, setRecipients] = useState<CampaignRecipient[] | null>(null);
  const [recipientsLoading, setRecipientsLoading] = useState(false);

  const canManage = user?.role === "business_owner" || user?.role === "manager";

  async function refreshAll() {
    try {
      const [templatesRes, segmentsRes, campaignsRes] = await Promise.all([
        listTemplates(),
        listSegments(),
        listCampaigns(),
      ]);
      setTemplates(templatesRes.results);
      setSegments(segmentsRes.results);
      setCampaigns(campaignsRes.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load campaigns.");
    }
  }

  useEffect(() => {
    if (!ready) return;
    listBusinesses()
      .then((res) => setBusinessId(res.results[0]?.id ?? null))
      .catch(() => {
        /* create forms just stay disabled without a business id */
      });
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll();
    const interval = setInterval(refreshAll, POLL_MS);
    return () => clearInterval(interval);
  }, [ready]);

  async function handleCreateTemplate(e: React.FormEvent) {
    e.preventDefault();
    if (!businessId) return;
    setError(null);
    setSuccess(null);
    setSubmittingTemplate(true);
    try {
      await createTemplate({ business: businessId, ...templateForm });
      setSuccess(`Template "${templateForm.name}" created as a draft.`);
      setTemplateForm(emptyTemplateForm);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create template.");
    } finally {
      setSubmittingTemplate(false);
    }
  }

  function startEditTemplate(t: MessageTemplate) {
    setEditingTemplateId(t.id);
    setTemplateEdit({
      status: t.status,
      whatsapp_template_name: t.whatsapp_template_name,
      rejection_reason: t.rejection_reason,
    });
  }

  async function handleSaveTemplate(id: string) {
    setError(null);
    try {
      await updateTemplate(id, templateEdit);
      setEditingTemplateId(null);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update template.");
    }
  }

  async function handleCreateSegment(e: React.FormEvent) {
    e.preventDefault();
    if (!businessId) return;
    setError(null);
    setSuccess(null);
    setSubmittingSegment(true);
    try {
      await createSegment({
        business: businessId,
        name: segmentForm.name,
        description: segmentForm.description || undefined,
        filters: {
          statuses: segmentForm.statuses.length ? segmentForm.statuses : undefined,
          sources: segmentForm.sources.length ? segmentForm.sources : undefined,
          tags: segmentForm.tags
            ? segmentForm.tags.split(",").map((t) => t.trim()).filter(Boolean)
            : undefined,
        },
      });
      setSuccess(`Segment "${segmentForm.name}" created.`);
      setSegmentForm(emptySegmentForm);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create segment.");
    } finally {
      setSubmittingSegment(false);
    }
  }

  async function handleDeleteSegment(segment: Segment) {
    setError(null);
    try {
      await deleteSegment(segment.id);
      if (previewId === segment.id) setPreviewId(null);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete segment.");
    }
  }

  async function handleTogglePreview(segment: Segment) {
    if (previewId === segment.id) {
      setPreviewId(null);
      setPreview(null);
      return;
    }
    setPreviewId(segment.id);
    setPreview(null);
    setPreviewLoading(true);
    try {
      const res = await previewSegment(segment.id);
      setPreview(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to preview segment.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleCreateCampaign(e: React.FormEvent) {
    e.preventDefault();
    if (!businessId) return;
    setError(null);
    setSuccess(null);
    setSubmittingCampaign(true);
    try {
      await createCampaign({
        business: businessId,
        segment: campaignForm.segment,
        template: campaignForm.template,
        name: campaignForm.name,
        template_variables: campaignForm.template_variables
          ? campaignForm.template_variables.split(",").map((v) => v.trim())
          : undefined,
        scheduled_at: campaignForm.scheduled_at || undefined,
      });
      setSuccess(`Campaign "${campaignForm.name}" created as a draft.`);
      setCampaignForm(emptyCampaignForm);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create campaign.");
    } finally {
      setSubmittingCampaign(false);
    }
  }

  async function handleSend(campaign: Campaign) {
    setError(null);
    setSuccess(null);
    setSendingId(campaign.id);
    try {
      await sendCampaign(campaign.id);
      setSuccess(`Sending "${campaign.name}"…`);
      await refreshAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send campaign.");
    } finally {
      setSendingId(null);
    }
  }

  async function handleToggleRecipients(campaign: Campaign) {
    if (expandedCampaignId === campaign.id) {
      setExpandedCampaignId(null);
      setRecipients(null);
      return;
    }
    setExpandedCampaignId(campaign.id);
    setRecipients(null);
    setRecipientsLoading(true);
    try {
      const res = await listCampaignRecipients(campaign.id);
      setRecipients(res.results);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load recipients.");
    } finally {
      setRecipientsLoading(false);
    }
  }

  if (!ready || !user) {
    return <div className="flex flex-1 items-center justify-center text-zinc-500">Loading…</div>;
  }

  const approvedTemplates = templates?.filter((t) => t.status === "approved") ?? [];

  return (
    <DashboardShell
      user={user}
      title="Campaigns"
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
      <div className="space-y-10">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        {/* ── Templates ─────────────────────────────────────── */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Message Templates
          </h2>
          <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            Meta requires templates to be submitted and approved in Business Manager before use —
            record the real outcome here once you&apos;ve checked. Only <code>approved</code>{" "}
            templates can actually send a campaign.
          </p>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Category</th>
                  <th className="px-4 py-2 font-medium">Variables</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  {canManage && <th className="px-4 py-2 font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {templates?.map((t) => (
                  <Fragment key={t.id}>
                    <tr className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{t.name}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{t.category}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{t.variable_count}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${TEMPLATE_STATUS_STYLE[t.status]}`}
                        >
                          {t.status.replace("_", " ")}
                        </span>
                      </td>
                      {canManage && (
                        <td className="px-4 py-2">
                          <button
                            onClick={() =>
                              editingTemplateId === t.id ? setEditingTemplateId(null) : startEditTemplate(t)
                            }
                            className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                          >
                            {editingTemplateId === t.id ? "Cancel" : "Edit"}
                          </button>
                        </td>
                      )}
                    </tr>
                    {editingTemplateId === t.id && (
                      <tr className="border-b border-zinc-100 bg-zinc-50 last:border-0 dark:border-zinc-800 dark:bg-zinc-900/40">
                        <td colSpan={5} className="px-4 py-3">
                          <div className="grid gap-3 sm:grid-cols-3">
                            <div>
                              <label className={labelClass}>Approval status</label>
                              <select
                                value={templateEdit.status}
                                onChange={(e) =>
                                  setTemplateEdit({
                                    ...templateEdit,
                                    status: e.target.value as TemplateStatus,
                                  })
                                }
                                className={selectClass}
                              >
                                <option value="draft">Draft</option>
                                <option value="pending_approval">Pending Approval</option>
                                <option value="approved">Approved</option>
                                <option value="rejected">Rejected</option>
                              </select>
                            </div>
                            <Field
                              label="WhatsApp template name"
                              value={templateEdit.whatsapp_template_name}
                              onChange={(v) =>
                                setTemplateEdit({ ...templateEdit, whatsapp_template_name: v })
                              }
                            />
                            <Field
                              label="Rejection reason"
                              value={templateEdit.rejection_reason}
                              onChange={(v) => setTemplateEdit({ ...templateEdit, rejection_reason: v })}
                            />
                          </div>
                          <button
                            onClick={() => handleSaveTemplate(t.id)}
                            className="mt-3 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
                          >
                            Save
                          </button>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {templates?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No templates yet.
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
              Add a Template
            </h2>
            <form
              onSubmit={handleCreateTemplate}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Internal name"
                value={templateForm.name}
                onChange={(v) => setTemplateForm({ ...templateForm, name: v })}
                required
              />
              <Field
                label="WhatsApp template name (optional)"
                value={templateForm.whatsapp_template_name}
                onChange={(v) => setTemplateForm({ ...templateForm, whatsapp_template_name: v })}
              />
              <div>
                <label className={labelClass}>Category</label>
                <select
                  value={templateForm.category}
                  onChange={(e) =>
                    setTemplateForm({
                      ...templateForm,
                      category: e.target.value as MessageTemplate["category"],
                    })
                  }
                  className={selectClass}
                >
                  <option value="marketing">Marketing</option>
                  <option value="utility">Utility</option>
                  <option value="authentication">Authentication</option>
                </select>
              </div>
              <Field
                label="Language code"
                value={templateForm.language_code}
                onChange={(v) => setTemplateForm({ ...templateForm, language_code: v })}
              />
              <div className="sm:col-span-2">
                <label className={labelClass}>
                  Body text{" "}
                  <span className="font-normal text-zinc-400">
                    (use {"{{1}}"}, {"{{2}}"}, … for variables, matching Meta&apos;s syntax)
                  </span>
                </label>
                <textarea
                  required
                  rows={3}
                  value={templateForm.body_text}
                  onChange={(e) => setTemplateForm({ ...templateForm, body_text: e.target.value })}
                  className={selectClass + " resize-y"}
                />
              </div>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submittingTemplate || !businessId}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submittingTemplate ? "Creating…" : "Add Template"}
                </button>
              </div>
            </form>
          </section>
        )}

        {/* ── Segments ──────────────────────────────────────── */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Segments
          </h2>
          <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            Customer counts only ever include opted-in customers — a segment can never overstate who
            can actually be messaged.
          </p>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Filters</th>
                  <th className="px-4 py-2 font-medium">Opted-in Customers</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {segments?.map((s) => (
                  <Fragment key={s.id}>
                    <tr className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{s.name}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {[
                          s.filters.statuses?.length ? `status: ${s.filters.statuses.join(", ")}` : null,
                          s.filters.sources?.length ? `source: ${s.filters.sources.join(", ")}` : null,
                          s.filters.tags?.length ? `tags: ${s.filters.tags.join(", ")}` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "All opted-in customers"}
                      </td>
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{s.customer_count}</td>
                      <td className="px-4 py-2">
                        <div className="flex gap-3">
                          <button
                            onClick={() => handleTogglePreview(s)}
                            className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                          >
                            {previewId === s.id ? "Hide preview" : "Preview"}
                          </button>
                          {canManage && (
                            <button
                              onClick={() => handleDeleteSegment(s)}
                              className="text-sm font-medium text-red-600 hover:underline dark:text-red-400"
                            >
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {previewId === s.id && (
                      <tr className="border-b border-zinc-100 bg-zinc-50 last:border-0 dark:border-zinc-800 dark:bg-zinc-900/40">
                        <td colSpan={4} className="px-4 py-3">
                          {previewLoading && <p className="text-sm text-zinc-500">Loading…</p>}
                          {!previewLoading && preview && preview.sample.length === 0 && (
                            <p className="text-sm text-zinc-500">No matching opted-in customers.</p>
                          )}
                          {!previewLoading && preview && preview.sample.length > 0 && (
                            <ul className="space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                              {preview.sample.map((c) => (
                                <li key={c.id}>
                                  {c.name || "(no name)"} — {c.phone}
                                </li>
                              ))}
                              {preview.customer_count > preview.sample.length && (
                                <li className="text-zinc-500">
                                  …and {preview.customer_count - preview.sample.length} more.
                                </li>
                              )}
                            </ul>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {segments?.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-zinc-500">
                      No segments yet.
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
              Add a Segment
            </h2>
            <form
              onSubmit={handleCreateSegment}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Name"
                value={segmentForm.name}
                onChange={(v) => setSegmentForm({ ...segmentForm, name: v })}
                required
              />
              <Field
                label="Description (optional)"
                value={segmentForm.description}
                onChange={(v) => setSegmentForm({ ...segmentForm, description: v })}
              />
              <div>
                <label className={labelClass}>Lead status (any match, optional)</label>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                  {LEAD_STATUSES.map((status) => (
                    <label key={status} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={segmentForm.statuses.includes(status)}
                        onChange={(e) =>
                          setSegmentForm({
                            ...segmentForm,
                            statuses: e.target.checked
                              ? [...segmentForm.statuses, status]
                              : segmentForm.statuses.filter((s) => s !== status),
                          })
                        }
                        className="h-3.5 w-3.5 rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      {status}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className={labelClass}>Source (any match, optional)</label>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                  {CUSTOMER_SOURCES.map((source) => (
                    <label key={source} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={segmentForm.sources.includes(source)}
                        onChange={(e) =>
                          setSegmentForm({
                            ...segmentForm,
                            sources: e.target.checked
                              ? [...segmentForm.sources, source]
                              : segmentForm.sources.filter((s) => s !== source),
                          })
                        }
                        className="h-3.5 w-3.5 rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500"
                      />
                      {source}
                    </label>
                  ))}
                </div>
              </div>
              <div className="sm:col-span-2">
                <Field
                  label="Tags (comma-separated, any match, optional)"
                  value={segmentForm.tags}
                  onChange={(v) => setSegmentForm({ ...segmentForm, tags: v })}
                />
              </div>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submittingSegment || !businessId}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submittingSegment ? "Creating…" : "Add Segment"}
                </button>
              </div>
            </form>
          </section>
        )}

        {/* ── Campaigns ─────────────────────────────────────── */}
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Campaigns
          </h2>
          <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Recipients</th>
                  <th className="px-4 py-2 font-medium">Sent / Failed / Skipped</th>
                  <th className="px-4 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns?.map((c) => (
                  <Fragment key={c.id}>
                    <tr className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                      <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{c.name}</td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${CAMPAIGN_STATUS_STYLE[c.status]}`}
                          title={c.status === "failed" ? c.error_message : undefined}
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">{c.recipient_count}</td>
                      <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                        {c.sent_count} / {c.failed_count} / {c.skipped_count}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-3">
                          {canManage && (c.status === "draft" || c.status === "scheduled") && (
                            <button
                              onClick={() => handleSend(c)}
                              disabled={sendingId === c.id}
                              className="text-sm font-medium text-emerald-600 hover:underline disabled:opacity-60 dark:text-emerald-400"
                            >
                              {sendingId === c.id ? "Sending…" : "Send"}
                            </button>
                          )}
                          <button
                            onClick={() => handleToggleRecipients(c)}
                            className="text-sm font-medium text-zinc-600 hover:underline dark:text-zinc-400"
                          >
                            {expandedCampaignId === c.id ? "Hide recipients" : "Recipients"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedCampaignId === c.id && (
                      <tr className="border-b border-zinc-100 bg-zinc-50 last:border-0 dark:border-zinc-800 dark:bg-zinc-900/40">
                        <td colSpan={5} className="px-4 py-3">
                          {c.status === "failed" && c.error_message && (
                            <p className="mb-2 text-sm text-red-600 dark:text-red-400">
                              {c.error_message}
                            </p>
                          )}
                          {recipientsLoading && <p className="text-sm text-zinc-500">Loading…</p>}
                          {!recipientsLoading && recipients?.length === 0 && (
                            <p className="text-sm text-zinc-500">
                              No recipients yet{c.status === "draft" ? " — not sent." : "."}
                            </p>
                          )}
                          {!recipientsLoading && recipients && recipients.length > 0 && (
                            <table className="w-full text-left text-sm">
                              <thead className="text-zinc-500 dark:text-zinc-400">
                                <tr>
                                  <th className="py-1 pr-4 font-medium">Customer</th>
                                  <th className="py-1 pr-4 font-medium">Status</th>
                                  <th className="py-1 pr-4 font-medium">Detail</th>
                                </tr>
                              </thead>
                              <tbody>
                                {recipients.map((r) => (
                                  <tr key={r.id}>
                                    <td className="py-1 pr-4 text-zinc-900 dark:text-zinc-100">
                                      {r.customer_name || r.customer_phone}
                                    </td>
                                    <td className="py-1 pr-4 text-zinc-500 dark:text-zinc-400">
                                      {r.status}
                                    </td>
                                    <td className="py-1 pr-4 text-zinc-500 dark:text-zinc-400">
                                      {r.skip_reason || r.error_message || "—"}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {campaigns?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                      No campaigns yet — create one below.
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
              Create a Campaign
            </h2>
            {approvedTemplates.length === 0 && (
              <p className="mb-3 text-xs text-amber-600 dark:text-amber-400">
                No approved templates yet — a campaign can be created against a draft template, but
                sending it will fail until the template is marked approved above.
              </p>
            )}
            <form
              onSubmit={handleCreateCampaign}
              className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <Field
                label="Name"
                value={campaignForm.name}
                onChange={(v) => setCampaignForm({ ...campaignForm, name: v })}
                required
              />
              <div>
                <label className={labelClass}>Segment</label>
                <select
                  required
                  value={campaignForm.segment}
                  onChange={(e) => setCampaignForm({ ...campaignForm, segment: e.target.value })}
                  className={selectClass}
                >
                  <option value="">Select a segment…</option>
                  {segments?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.customer_count})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelClass}>Template</label>
                <select
                  required
                  value={campaignForm.template}
                  onChange={(e) => setCampaignForm({ ...campaignForm, template: e.target.value })}
                  className={selectClass}
                >
                  <option value="">Select a template…</option>
                  {templates?.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.status})
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="Template variables (comma-separated, optional)"
                value={campaignForm.template_variables}
                onChange={(v) => setCampaignForm({ ...campaignForm, template_variables: v })}
              />
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submittingCampaign || !businessId}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submittingCampaign ? "Creating…" : "Create Campaign"}
                </button>
              </div>
            </form>
          </section>
        )}
      </div>
    </DashboardShell>
  );
}
