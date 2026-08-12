import { Field } from "@/components/Field";
import type { MessageTemplate, Segment } from "@/types";
import { labelClass, selectClass } from "./shared";

export interface CampaignFormState {
  name: string;
  segment: string;
  template: string;
  template_variables: string;
  scheduled_at: string;
}

export const emptyCampaignForm: CampaignFormState = {
  name: "",
  segment: "",
  template: "",
  template_variables: "",
  scheduled_at: "",
};

export function CampaignForm({
  value,
  onChange,
  segments,
  templates,
  approvedTemplateCount,
  onSubmit,
  submitting,
  disabled,
}: {
  value: CampaignFormState;
  onChange: (next: CampaignFormState) => void;
  segments: Segment[] | null;
  templates: MessageTemplate[] | null;
  approvedTemplateCount: number;
  onSubmit: (e: React.FormEvent) => void;
  submitting: boolean;
  disabled: boolean;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Create a Campaign
      </h2>
      {approvedTemplateCount === 0 && (
        <p className="mb-3 text-xs text-amber-600 dark:text-amber-400">
          No approved templates yet — a campaign can be created against a draft template, but sending
          it will fail until the template is marked approved above.
        </p>
      )}
      <form
        onSubmit={onSubmit}
        className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
      >
        <Field
          label="Name"
          value={value.name}
          onChange={(v) => onChange({ ...value, name: v })}
          required
        />
        <div>
          <label className={labelClass}>Segment</label>
          <select
            required
            value={value.segment}
            onChange={(e) => onChange({ ...value, segment: e.target.value })}
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
            value={value.template}
            onChange={(e) => onChange({ ...value, template: e.target.value })}
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
          value={value.template_variables}
          onChange={(v) => onChange({ ...value, template_variables: v })}
        />
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={submitting || disabled}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Creating…" : "Create Campaign"}
          </button>
        </div>
      </form>
    </section>
  );
}
