import { Fragment } from "react";

import type { Campaign, CampaignRecipient } from "@/types";
import { CAMPAIGN_STATUS_STYLE } from "./shared";

export function CampaignsSection({
  campaigns,
  canManage,
  sendingId,
  expandedCampaignId,
  recipients,
  recipientsLoading,
  onSend,
  onToggleRecipients,
}: {
  campaigns: Campaign[] | null;
  canManage: boolean;
  sendingId: string | null;
  expandedCampaignId: string | null;
  recipients: CampaignRecipient[] | null;
  recipientsLoading: boolean;
  onSend: (c: Campaign) => void;
  onToggleRecipients: (c: Campaign) => void;
}) {
  return (
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
                          onClick={() => onSend(c)}
                          disabled={sendingId === c.id}
                          className="text-sm font-medium text-emerald-600 hover:underline disabled:opacity-60 dark:text-emerald-400"
                        >
                          {sendingId === c.id ? "Sending…" : "Send"}
                        </button>
                      )}
                      <button
                        onClick={() => onToggleRecipients(c)}
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
                        <p className="mb-2 text-sm text-red-600 dark:text-red-400">{c.error_message}</p>
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
                                <td className="py-1 pr-4 text-zinc-500 dark:text-zinc-400">{r.status}</td>
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
  );
}
