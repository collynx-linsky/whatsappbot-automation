// A pulsing placeholder block that preserves layout while real content
// loads — used for in-page data (tables, stat rows), not full-page
// transitions (see PageLoading for that). Respects prefers-reduced-motion
// via the global rule in globals.css, so `animate-pulse` degrades to a
// static block rather than being distracting for users who asked for less
// motion.
export function Skeleton({ className = "" }: { className?: string }) {
  // bg-border (not bg-page) — a skeleton lives inside a surface (card,
  // table), so it needs to contrast against that, not match the page
  // canvas behind it.
  return <div className={`animate-pulse rounded-md bg-border ${className}`} aria-hidden />;
}
