import { Field } from "@/components/Field";
import type { CustomerSource, LeadStatus } from "@/types";
import { CUSTOMER_SOURCES, LEAD_STATUSES, labelClass } from "./shared";

export interface SegmentFormState {
  name: string;
  description: string;
  statuses: LeadStatus[];
  sources: CustomerSource[];
  tags: string;
}

export const emptySegmentForm: SegmentFormState = {
  name: "",
  description: "",
  statuses: [],
  sources: [],
  tags: "",
};

export function SegmentForm({
  value,
  onChange,
  onSubmit,
  submitting,
  disabled,
}: {
  value: SegmentFormState;
  onChange: (next: SegmentFormState) => void;
  onSubmit: (e: React.FormEvent) => void;
  submitting: boolean;
  disabled: boolean;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Add a Segment
      </h2>
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
        <Field
          label="Description (optional)"
          value={value.description}
          onChange={(v) => onChange({ ...value, description: v })}
        />
        <div>
          <label className={labelClass}>Lead status (any match, optional)</label>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
            {LEAD_STATUSES.map((status) => (
              <label key={status} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={value.statuses.includes(status)}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      statuses: e.target.checked
                        ? [...value.statuses, status]
                        : value.statuses.filter((s) => s !== status),
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
                  checked={value.sources.includes(source)}
                  onChange={(e) =>
                    onChange({
                      ...value,
                      sources: e.target.checked
                        ? [...value.sources, source]
                        : value.sources.filter((s) => s !== source),
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
            value={value.tags}
            onChange={(v) => onChange({ ...value, tags: v })}
          />
        </div>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={submitting || disabled}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Creating…" : "Add Segment"}
          </button>
        </div>
      </form>
    </section>
  );
}
