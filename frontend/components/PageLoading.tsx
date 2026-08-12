// The full-page "checking your session" state every dashboard/admin page
// shows before useRequireAuth() resolves — was 11 identical copies of
// plain gray "Loading…" text. This is a blocking gate, not a page with a
// known layout yet, so a branded pulse reads better here than trying to
// fake a content skeleton for a page shape we don't know yet.
export function PageLoading() {
  return (
    <div className="flex flex-1 items-center justify-center bg-page">
      <div className="flex flex-col items-center gap-3">
        <span className="flex h-10 w-10 animate-pulse items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
          W
        </span>
        <span className="text-sm text-ink-muted">Loading…</span>
      </div>
    </div>
  );
}
