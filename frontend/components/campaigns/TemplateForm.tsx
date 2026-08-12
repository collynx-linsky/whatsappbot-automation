import { Field } from "@/components/Field";
import type { MessageTemplate } from "@/types";
import { labelClass, selectClass } from "./shared";

export interface TemplateFormState {
  name: string;
  whatsapp_template_name: string;
  category: MessageTemplate["category"];
  language_code: string;
  body_text: string;
}

export const emptyTemplateForm: TemplateFormState = {
  name: "",
  whatsapp_template_name: "",
  category: "marketing",
  language_code: "en_US",
  body_text: "",
};

export function TemplateForm({
  value,
  onChange,
  onSubmit,
  submitting,
  disabled,
}: {
  value: TemplateFormState;
  onChange: (next: TemplateFormState) => void;
  onSubmit: (e: React.FormEvent) => void;
  submitting: boolean;
  disabled: boolean;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Add a Template
      </h2>
      <form
        onSubmit={onSubmit}
        className="grid gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
      >
        <Field
          label="Internal name"
          value={value.name}
          onChange={(v) => onChange({ ...value, name: v })}
          required
        />
        <Field
          label="WhatsApp template name (optional)"
          value={value.whatsapp_template_name}
          onChange={(v) => onChange({ ...value, whatsapp_template_name: v })}
        />
        <div>
          <label className={labelClass}>Category</label>
          <select
            value={value.category}
            onChange={(e) => onChange({ ...value, category: e.target.value as MessageTemplate["category"] })}
            className={selectClass}
          >
            <option value="marketing">Marketing</option>
            <option value="utility">Utility</option>
            <option value="authentication">Authentication</option>
          </select>
        </div>
        <Field
          label="Language code"
          value={value.language_code}
          onChange={(v) => onChange({ ...value, language_code: v })}
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
            value={value.body_text}
            onChange={(e) => onChange({ ...value, body_text: e.target.value })}
            className={selectClass + " resize-y"}
          />
        </div>
        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={submitting || disabled}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Creating…" : "Add Template"}
          </button>
        </div>
      </form>
    </section>
  );
}
