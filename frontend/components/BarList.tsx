// Minimal horizontal bar chart — no charting library in this codebase, and
// this is the one chart form (thin bars, direct value labels, sequential
// single-hue by default) that a handful of <div> rows can render correctly.
//
// - Bars share one color by default (a single "count" series across
//   categories — e.g. customers per funnel stage) — this is what "sequential,
//   one hue" means for a bar list, not a rainbow per category.
// - Pass `color` per item only when the categories are genuinely different
//   entities (e.g. messages by sender type) — color then carries identity,
//   never rank, and every item still gets a printed value so nothing reads
//   color-only.
export interface BarListItem {
  key: string;
  label: string;
  value: number;
  color?: string;
}

const DEFAULT_COLOR = "#059669"; // emerald-600 — matches the app's brand accent

export function BarList({
  items,
  valueFormat,
  emptyLabel = "No data yet.",
}: {
  items: BarListItem[];
  valueFormat?: (value: number) => string;
  emptyLabel?: string;
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const format = valueFormat ?? ((v: number) => String(v));

  if (items.length === 0 || items.every((i) => i.value === 0)) {
    return <p className="py-4 text-center text-sm text-zinc-500 dark:text-zinc-400">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-2.5">
      {items.map((item) => (
        <li key={item.key} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 text-sm">
          <span className="truncate text-zinc-600 dark:text-zinc-400" title={item.label}>
            {item.label}
          </span>
          <span className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <span
              className="block h-full rounded-full"
              style={{
                width: `${(item.value / max) * 100}%`,
                backgroundColor: item.color ?? DEFAULT_COLOR,
              }}
            />
          </span>
          <span className="w-14 text-right tabular-nums text-zinc-900 dark:text-zinc-100">
            {format(item.value)}
          </span>
        </li>
      ))}
    </ul>
  );
}

// Small inline legend — used above a BarList only when `color` is passed
// per item (identity-coded), so the color↔category mapping is never
// color-only even before reading down to the direct value labels.
export function BarListLegend({ items }: { items: { key: string; label: string; color: string }[] }) {
  return (
    <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
      {items.map((item) => (
        <span key={item.key} className="flex items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: item.color }}
            aria-hidden
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}
