// A minimal single-hue line+area sparkline for a short time series (e.g.
// 30-day signup trend) — change-over-time is a line's job, not a bar
// chart's. No charting library in this codebase, so this is hand-rolled
// SVG; kept intentionally small (one series, one hue, no axes) since a
// sparkline's whole point is "shape at a glance," not readable ticks.
export function Sparkline({
  data,
  height = 48,
}: {
  data: { date: string; count: number }[];
  height?: number;
}) {
  const width = 300;
  const max = Math.max(1, ...data.map((d) => d.count));
  const total = data.reduce((sum, d) => sum + d.count, 0);

  if (data.length === 0) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">No signups in this period.</p>;
  }

  const points = data.map((d, i) => {
    const x = data.length > 1 ? (i / (data.length - 1)) * width : width / 2;
    const y = height - (d.count / max) * (height - 4) - 2;
    return [x, y] as const;
  });
  const line = points.map(([x, y]) => `${x},${y}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-12 w-full"
        role="img"
        aria-label={`${total} new tenant${total === 1 ? "" : "s"} over the last ${data.length} days`}
      >
        <polygon points={area} fill="#059669" fillOpacity={0.12} />
        <polyline points={line} fill="none" stroke="#059669" strokeWidth={2} vectorEffect="non-scaling-stroke" />
      </svg>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
        {total} new tenant{total === 1 ? "" : "s"} · {data[0]?.date} – {data[data.length - 1]?.date}
      </p>
    </div>
  );
}
