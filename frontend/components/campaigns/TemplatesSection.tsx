import { Fragment } from "react";

import { Field } from "@/components/Field";
import type { MessageTemplate, TemplateStatus } from "@/types";
import { labelClass, selectClass, TEMPLATE_STATUS_STYLE } from "./shared";

export interface TemplateEditState {
  status: TemplateStatus;
  whatsapp_template_name: string;
  rejection_reason: string;
}

export function TemplatesSection({
  templates,
  canManage,
  editingTemplateId,
  templateEdit,
  onStartEdit,
  onCancelEdit,
  onEditChange,
  onSaveEdit,
}: {
  templates: MessageTemplate[] | null;
  canManage: boolean;
  editingTemplateId: string | null;
  templateEdit: TemplateEditState;
  onStartEdit: (t: MessageTemplate) => void;
  onCancelEdit: () => void;
  onEditChange: (next: TemplateEditState) => void;
  onSaveEdit: (id: string) => void;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Message Templates
      </h2>
      <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        Meta requires templates to be submitted and approved in Business Manager before use — record
        the real outcome here once you&apos;ve checked. Only <code>approved</code> templates can
        actually send a campaign.
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
                        onClick={() => (editingTemplateId === t.id ? onCancelEdit() : onStartEdit(t))}
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
                              onEditChange({ ...templateEdit, status: e.target.value as TemplateStatus })
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
                          onChange={(v) => onEditChange({ ...templateEdit, whatsapp_template_name: v })}
                        />
                        <Field
                          label="Rejection reason"
                          value={templateEdit.rejection_reason}
                          onChange={(v) => onEditChange({ ...templateEdit, rejection_reason: v })}
                        />
                      </div>
                      <button
                        onClick={() => onSaveEdit(t.id)}
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
  );
}
