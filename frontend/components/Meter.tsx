// A used-vs-capacity track — distinct from BarList's categorical
// comparison: this is one quantity against its own ceiling, so color
// encodes proximity to the limit (good/warning/critical), not identity.
// Matches the dataviz skill's reserved status palette: green under 70%,
// amber 70–90%, red at/above 90% — and a status color is never the only
// signal, the used/limit numbers are always printed too.
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
    ratio >= 0.9 ? "#dc2626" /* red-600 */ : ratio >= 0.7 ? "#d97706" /* amber-600 */ : "#059669"; /* emerald-600 */

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
        <span className="tabular-nums text-zinc-500 dark:text-zinc-400">
          {used} {unlimited ? "" : `/ ${limit}`}
          {unlimited && <span className="ml-1 text-emerald-600 dark:text-emerald-400">Unlimited</span>}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
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
