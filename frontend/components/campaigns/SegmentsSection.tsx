import { Fragment } from "react";

import type { Segment, SegmentPreview } from "@/types";

export function SegmentsSection({
  segments,
  canManage,
  previewId,
  preview,
  previewLoading,
  onTogglePreview,
  onDelete,
}: {
  segments: Segment[] | null;
  canManage: boolean;
  previewId: string | null;
  preview: SegmentPreview | null;
  previewLoading: boolean;
  onTogglePreview: (s: Segment) => void;
  onDelete: (s: Segment) => void;
}) {
  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Segments
      </h2>
      <p className="mb-3 -mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        Customer counts only ever include opted-in customers — a segment can never overstate who can
        actually be messaged.
      </p>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Filters</th>
              <th className="px-4 py-2 font-medium">Opted-in Customers</th>
              <th className="px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {segments?.map((s) => (
              <Fragment key={s.id}>
                <tr className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                  <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{s.name}</td>
                  <td className="px-4 py-2 text-zinc-500 dark:text-zinc-400">
                    {[
                      s.filters.statuses?.length ? `status: ${s.filters.statuses.join(", ")}` : null,
                      s.filters.sources?.length ? `source: ${s.filters.sources.join(", ")}` : null,
                      s.filters.tags?.length ? `tags: ${s.filters.tags.join(", ")}` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "All opted-in customers"}
                  </td>
                  <td className="px-4 py-2 text-zinc-900 dark:text-zinc-100">{s.customer_count}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-3">
                      <button
                        onClick={() => onTogglePreview(s)}
                        className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
                      >
                        {previewId === s.id ? "Hide preview" : "Preview"}
                      </button>
                      {canManage && (
                        <button
                          onClick={() => onDelete(s)}
                          className="text-sm font-medium text-red-600 hover:underline dark:text-red-400"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {previewId === s.id && (
                  <tr className="border-b border-zinc-100 bg-zinc-50 last:border-0 dark:border-zinc-800 dark:bg-zinc-900/40">
                    <td colSpan={4} className="px-4 py-3">
                      {previewLoading && <p className="text-sm text-zinc-500">Loading…</p>}
                      {!previewLoading && preview && preview.sample.length === 0 && (
                        <p className="text-sm text-zinc-500">No matching opted-in customers.</p>
                      )}
                      {!previewLoading && preview && preview.sample.length > 0 && (
                        <ul className="space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                          {preview.sample.map((c) => (
                            <li key={c.id}>
                              {c.name || "(no name)"} — {c.phone}
                            </li>
                          ))}
                          {preview.customer_count > preview.sample.length && (
                            <li className="text-zinc-500">
                              …and {preview.customer_count - preview.sample.length} more.
                            </li>
                          )}
                        </ul>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {segments?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-zinc-500">
                  No segments yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
