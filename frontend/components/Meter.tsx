// A used-vs-capacity track — distinct from BarList's categorical
// comparison: this is one quantity against its own ceiling, so color
// encodes proximity to the limit (good/warning/critical), not identity.
// Uses the semantic status tokens (globals.css) rather than fixed hex —
// each has its own validated light/dark value, unlike the flat hex this
// used before. A status color is never the only signal: the used/limit
// numbers are always printed too.
export function Meter({
  label,
  used,
  limit,
  unlimited,
}: {
  label: string;
  used: number;
  limit: number;
  unlimited: boolean;
}) {
  const ratio = unlimited || limit === 0 ? 0 : Math.min(1, used / limit);
  const color =
    ratio >= 0.9
      ? "var(--color-danger)"
      : ratio >= 0.7
        ? "var(--color-warning)"
        : "var(--color-success)";

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="font-medium text-ink-secondary">{label}</span>
        <span className="tabular-nums text-ink-muted">
          {used} {unlimited ? "" : `/ ${limit}`}
          {unlimited && <span className="ml-1 text-primary">Unlimited</span>}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-page">
        {!unlimited && (
          <div
            data-testid="meter-fill"
            className="h-full rounded-full transition-[width]"
            style={{ width: `${ratio * 100}%`, backgroundColor: color }}
          />
        )}
      </div>
    </div>
  );
}
