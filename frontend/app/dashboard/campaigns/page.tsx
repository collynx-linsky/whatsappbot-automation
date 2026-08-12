"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/Alert";
import { CampaignForm, emptyCampaignForm, type CampaignFormState } from "@/components/campaigns/CampaignForm";
import { CampaignsSection } from "@/components/campaigns/CampaignsSection";
import { SegmentForm, emptySegmentForm, type SegmentFormState } from "@/components/campaigns/SegmentForm";
import { SegmentsSection } from "@/components/campaigns/SegmentsSection";
import { TemplateForm, emptyTemplateForm, type TemplateFormState } from "@/components/campaigns/TemplateForm";
import { TemplatesSection, type TemplateEditState } from "@/components/campaigns/TemplatesSection";
import { DashboardShell } from "@/components/DashboardShell";
import { PageLoading } from "@/components/PageLoading";
import {
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
import { getErrorMessage } from "@/lib/errors";
import { DASHBOARD_NAV } from "@/lib/navigation";
import { useRequireAuth } from "@/lib/useAuth";
import type { Campaign, CampaignRecipient, MessageTemplate, Segment, SegmentPreview } from "@/types";

// Campaigns send async via Celery, same reasoning as the knowledge base's
// processing poll — no real-time channel on this backend.
const POLL_MS = 5000;

// This page is the composition/orchestration layer only — all state,
// data-fetching, and mutation handlers live here; rendering for each of
// the three entities (templates/segments/campaigns) lives in
// components/campaigns/*. Was one 862-line file; refactored into this
// plus 6 focused subcomponents, same route, same functionality.
export default function CampaignsPage() {
  const { user, ready } = useRequireAuth();
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<MessageTemplate[] | null>(null);
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [templateForm, setTemplateForm] = useState<TemplateFormState>(emptyTemplateForm);
  const [submittingTemplate, setSubmittingTemplate] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [templateEdit, setTemplateEdit] = useState<TemplateEditState>({
    status: "draft",
    whatsapp_template_name: "",
    rejection_reason: "",
  });

  const [segmentForm, setSegmentForm] = useState<SegmentFormState>(emptySegmentForm);
  const [submittingSegment, setSubmittingSegment] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [preview, setPreview] = useState<SegmentPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [campaignForm, setCampaignForm] = useState<CampaignFormState>(emptyCampaignForm);
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
      setError(getErrorMessage(err, "Failed to load campaigns."));
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
      setError(getErrorMessage(err, "Failed to create template."));
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
      setError(getErrorMessage(err, "Failed to update template."));
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
      setError(getErrorMessage(err, "Failed to create segment."));
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
      setError(getErrorMessage(err, "Failed to delete segment."));
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
      setError(getErrorMessage(err, "Failed to preview segment."));
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
      setError(getErrorMessage(err, "Failed to create campaign."));
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
      setError(getErrorMessage(err, "Failed to send campaign."));
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
      setError(getErrorMessage(err, "Failed to load recipients."));
    } finally {
      setRecipientsLoading(false);
    }
  }

  if (!ready || !user) {
    return <PageLoading />;
  }

  const approvedTemplateCount = templates?.filter((t) => t.status === "approved").length ?? 0;

  return (
    <DashboardShell user={user} title="Campaigns" nav={DASHBOARD_NAV}>
      <div className="space-y-10">
        {error && <Alert kind="error" message={error} />}
        {success && <Alert kind="success" message={success} />}

        <TemplatesSection
          templates={templates}
          canManage={canManage}
          editingTemplateId={editingTemplateId}
          templateEdit={templateEdit}
          onStartEdit={startEditTemplate}
          onCancelEdit={() => setEditingTemplateId(null)}
          onEditChange={setTemplateEdit}
          onSaveEdit={handleSaveTemplate}
        />

        {canManage && (
          <TemplateForm
            value={templateForm}
            onChange={setTemplateForm}
            onSubmit={handleCreateTemplate}
            submitting={submittingTemplate}
            disabled={!businessId}
          />
        )}

        <SegmentsSection
          segments={segments}
          canManage={canManage}
          previewId={previewId}
          preview={preview}
          previewLoading={previewLoading}
          onTogglePreview={handleTogglePreview}
          onDelete={handleDeleteSegment}
        />

        {canManage && (
          <SegmentForm
            value={segmentForm}
            onChange={setSegmentForm}
            onSubmit={handleCreateSegment}
            submitting={submittingSegment}
            disabled={!businessId}
          />
        )}

        <CampaignsSection
          campaigns={campaigns}
          canManage={canManage}
          sendingId={sendingId}
          expandedCampaignId={expandedCampaignId}
          recipients={recipients}
          recipientsLoading={recipientsLoading}
          onSend={handleSend}
          onToggleRecipients={handleToggleRecipients}
        />

        {canManage && (
          <CampaignForm
            value={campaignForm}
            onChange={setCampaignForm}
            segments={segments}
            templates={templates}
            approvedTemplateCount={approvedTemplateCount}
            onSubmit={handleCreateCampaign}
            submitting={submittingCampaign}
            disabled={!businessId}
          />
        )}
      </div>
    </DashboardShell>
  );
}
