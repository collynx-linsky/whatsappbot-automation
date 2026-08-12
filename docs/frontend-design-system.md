# Frontend design system

What this app's frontend is built from — tokens, shared components,
navigation architecture, and the specific accessibility bug this system
replaced. Written alongside the "premium enterprise transformation" pass
that introduced it; see `docs/ROADMAP.md` for that session's full summary.

## Philosophy

This is a real WhatsApp Business AI product, not a generic admin
template. The design language is deliberately restrained: one accent
color (emerald), one neutral scale (zinc), thin borders over heavy
shadows, dense information layout over decorative whitespace. Nothing
here is copied from another product's visual identity — the token names
and component shapes are original, even where the underlying palette
(zinc/emerald) predates this pass.

Explicitly avoided, on purpose: gradients, glassmorphism, oversized
rounded cards, animation for its own sake. The bar for adding motion or
visual weight is "does this help someone do their job faster," not "does
this look impressive in a screenshot."

## Tokens (`app/globals.css`)

A semantic layer over Tailwind's raw `zinc-*`/`emerald-*` scale — **not a
replacement for it**. Existing pages keep their original utility classes
(already audited as consistent app-wide); new and refactored components
are built against the tokens instead. Every token has an explicit light
**and** dark value — the previous approach (one fixed hex assumed to work
in both modes) is exactly the bug documented below.

| Category | Tokens | Notes |
|---|---|---|
| Brand/action | `--color-primary(-hover/-active)`, `--color-secondary(-hover)` | Primary is emerald; dark mode steps one notch lighter (500 vs 600) to hold contrast on a dark surface |
| Status | `--color-success/-warning/-danger/-info` (+ `-surface` variants) | Dark values are different Tailwind steps, not the same hex reused — `warning`/`danger` in particular need lighter steps on dark to stay legible |
| Surfaces | `--color-page`, `--color-surface`, `--color-surface-elevated` | `page` = app canvas, `surface` = cards/panels, `surface-elevated` = dialogs/dropdowns (one step up from `surface` in dark mode, so an elevated panel visibly sits "above" the page) |
| Borders | `--color-border`, `--color-divider` | Divider is the lighter hairline |
| Text | `--color-ink`, `--color-ink-secondary`, `--color-ink-muted`, `--color-ink-disabled` | Named `ink`, not `text`, specifically to avoid Tailwind generating the redundant `text-text-primary` utility |
| Elevation | `--shadow-card`, `--shadow-elevated` | Two steps only — this app doesn't need a 5-step shadow scale |
| Charts | `--chart-1` … `--chart-5` | See "Categorical chart colors" below — fixed order, never reassigned |

Declared once in `:root`, overridden under `@media (prefers-color-scheme:
dark)`. This app has no manual light/dark toggle (OS preference only), so
there's no `[data-theme]` variant to worry about.

`@theme inline` re-exposes each role as a real Tailwind utility
(`bg-primary`, `text-ink-muted`, `border-border`, …) — same mechanism the
file already used for `--background`/`--color-background` before this
pass, just extended to a full role set.

### Categorical chart colors — a real bug this pass found and fixed

The message-sender-type chart (Analytics page, `BarList`) used one fixed
hex per category for both light and dark mode. Running it through the
dataviz skill's actual validator (not eyeballing it) found two real
failures:

- **Light mode**: the "System" color (zinc-400) failed the chroma floor —
  it read as gray, not as a color, so it didn't register as a distinct
  category at a glance.
- **Dark mode**: "System" and "Campaign" (amber-500) both failed the
  lightness band — washed out against the dark surface.

Fixed by finding a 5-hue set that validates as one set in **both** modes
(blue `#3b82f6`, emerald `#059669`, violet `#8b5cf6`, cyan `#0891b2`,
amber `#d97706` — cyan replaces the failing gray, amber steps one notch
darker) and declaring them as `--chart-1`..`--chart-5` tokens. This
specific 5-hex set happens to pass unchanged against both surfaces —
that's a validated result for this exact set, not an assumption; a future
6th slot needs its own light/dark check, run through
`scripts/validate_palette.js` from the dataviz skill, not picked by eye.

`Meter`'s status colors (used/limit thresholds) use the semantic
`--color-success/-warning/-danger` tokens instead — a different
validation class (status, not categorical) with its own light/dark steps.

## Shared components (`components/`)

| Component | Purpose |
|---|---|
| `Button.tsx` | Strict variant hierarchy: `primary`/`secondary`/`ghost`/`danger`, two sizes, built-in loading spinner. Not yet retrofit onto every existing page button (see "Known gaps" below) |
| `EmptyState.tsx` | Title + description + optional action + optional icon — replaces bare "No X yet." text. Wired into the WhatsApp page's connected-numbers panel; deliberately **not** forced into table `<td>` empty rows (see below) |
| `Skeleton.tsx` | A pulsing placeholder block for in-page data loading, respecting `prefers-reduced-motion` |
| `PageLoading.tsx` | The full-page "checking your session" gate every dashboard/admin page shows before `useRequireAuth()` resolves — replaces 11 identical copies of plain "Loading…" text |
| `CommandPalette.tsx` | Ctrl/Cmd+K global palette — see below |
| `Icons.tsx` | Shared hand-drawn SVG icon set (stroke-based, consistent 1.75 stroke width), used by both the marketing site and the dashboard sidebar — no icon library dependency |
| `DashboardShell.tsx` | The app shell: sidebar nav, mobile drawer, user menu, command palette mount point, page header, footer. Every dashboard/admin page renders through this |

### Command palette

Real, functional, and deliberately narrow in scope: it only navigates to
routes that actually exist (sourced from `lib/navigation.ts`, the same
list the sidebar uses) plus a "Log out" action. It does **not** provide
search across records — there's no backend search endpoint for it to call,
and building a palette that pretends to search things it can't actually
find would be exactly the kind of fabricated functionality this pass was
told not to introduce. If a real search API is ever built, this is where
it would plug in.

Opens on `Ctrl+K`/`Cmd+K` (and `/` when focus isn't in a text field),
closes on `Escape` or backdrop click, arrow-key navigable, returns focus
to the trigger element on close.

## Navigation architecture (`lib/navigation.ts`)

Previously: an identical `{label, href}[]` array copy-pasted into 9
separate page files, plus a *separate* href-keyed icon lookup table
inside `DashboardShell`. Both risks are gone — `DASHBOARD_NAV` is the one
list, each entry already carries its icon component, and every dashboard
page imports the same constant instead of hardcoding its own copy.

`/admin` deliberately does **not** use this list — it's a separate
single-route surface for `super_admin`, not a tenant-side module. Nothing
in this file enforces that boundary; the backend's `IsSuperAdmin`
permission class is the actual security control, same as everywhere else
in this app (frontend navigation is convenience, never authorization).

## Error handling (`lib/errors.ts`)

`getErrorMessage(err, fallback)` replaces the `err instanceof ApiError ?
err.message : "..."` pattern that was repeated 49 times across every
page's catch block. Behavior is identical — a real `ApiError` still shows
its real server message, anything else falls back to the caller's text —
just centralized so there's one place to get the `instanceof` check
right instead of 49.

## Testing

`components/__tests__/DashboardShell.test.tsx` covers nav rendering,
active-route highlighting, the `initials()` helper (one-word/multi-word/
empty names), the mobile drawer (open, close-on-nav-click,
close-on-backdrop-click), and logout. See `docs/testing.md` for the full
test-layer breakdown and the E2E account setup (now two accounts — a
business owner and, new this pass, a dedicated super admin, so
authenticated Playwright/visual-QA coverage can reach `/admin` too).

## Known gaps, stated honestly

- **`Button` isn't retrofit onto every existing page.** It's built,
  documented, and used by new code; wholesale-replacing dozens of already-
  working, already-tested inline button classNames across 13 pages was a
  real regression risk for no functional benefit this late in the pass,
  so it wasn't done. Text-link-style table actions (Edit/Delete/Preview)
  don't map cleanly onto `Button`'s filled-button variants anyway — that
  would need a `link` variant this component doesn't have yet.
- **`EmptyState` isn't in every empty-table `<td>`.** It's designed for
  spacious standalone panels (used on the WhatsApp page); squeezing an
  icon+title+description into a table cell would need different treatment
  than this component currently offers. The existing centered-text empty
  table rows are a legitimate, conventional pattern on their own.
- **Most small, contextual "Loading…" text spots weren't converted to
  skeletons** — e.g. a campaign's expandable recipients panel, a
  segment's expandable preview. These are non-blocking, layout-preserving,
  and small; the full-page auth-gate loading state (seen on every single
  page load) was the higher-value target and is done.
- **No notification center, no global search backend, no audit-log
  viewer UI.** None of these have a real backend endpoint to call yet —
  building frontend for them would mean fabricating data or faking
  functionality, which this pass was explicitly told not to do.
- **Mobile inbox two-pane fix is new and narrow in scope**: below `lg`,
  the conversation list and message thread now show one at a time (with
  a back control) instead of both panes fighting for a combined ~390px of
  width. Verified live against a real seeded conversation, both
  directions of navigation, and confirmed desktop is unaffected — but
  this is the only page that needed this particular pattern; no other
  page had a fixed-width multi-pane layout to begin with.
