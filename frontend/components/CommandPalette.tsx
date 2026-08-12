"use client";

// Global Cmd/Ctrl+K command palette. Deliberately navigation-only: every
// entry is a real route this user can already reach from the sidebar, or
// a real action (log out) — no fabricated search across entities that
// have no backend search endpoint. See docs/frontend-design-system.md.
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { IconLogout } from "@/components/Icons";
import { DASHBOARD_NAV, type NavItem } from "@/lib/navigation";

interface Command {
  id: string;
  label: string;
  hint?: string;
  icon: NavItem["icon"];
  run: () => void;
}

export function CommandPalette({ onLogout }: { onLogout: () => void | Promise<void> }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  const commands = useMemo<Command[]>(
    () => [
      ...DASHBOARD_NAV.map((item) => ({
        id: item.href,
        label: `Go to ${item.label}`,
        icon: item.icon,
        run: () => router.push(item.href),
      })),
      {
        id: "logout",
        label: "Log out",
        icon: IconLogout,
        run: () => onLogout(),
      },
    ],
    [router, onLogout],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.label.toLowerCase().includes(q));
  }, [commands, query]);

  const close = () => {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
    triggerRef.current?.focus();
  };

  // Global shortcut — Ctrl+K (Windows/Linux) or Cmd+K (Mac). Also opens on
  // "/" when focus isn't already in a text input, a common secondary
  // convention (mirrors GitHub/Linear) that costs nothing to support.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const isTypingTarget =
        e.target instanceof HTMLElement &&
        (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable);

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        triggerRef.current = document.activeElement as HTMLElement;
        setOpen((v) => !v);
        return;
      }
      if (e.key === "/" && !isTypingTarget && !open) {
        e.preventDefault();
        triggerRef.current = document.activeElement as HTMLElement;
        setOpen(true);
      }
      if (e.key === "Escape" && open) {
        close();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  function activate(cmd: Command) {
    close();
    cmd.run();
  }

  function onInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[activeIndex];
      if (cmd) activate(cmd);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          triggerRef.current = document.activeElement as HTMLElement;
          setOpen(true);
        }}
        className="flex w-full max-w-xs items-center gap-2 rounded-lg border border-border bg-page px-3 py-1.5 text-left text-sm text-ink-muted transition-colors hover:border-secondary hover:text-ink-secondary"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} className="h-4 w-4 shrink-0">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
        </svg>
        <span className="flex-1 truncate">Search or jump to…</span>
        <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[11px]">
          Ctrl K
        </kbd>
      </button>

      {open && (
        <div className="fixed inset-0 z-[60]" role="presentation">
          <div className="absolute inset-0 bg-zinc-900/50" onClick={close} aria-hidden />
          <div className="relative mx-auto mt-24 w-full max-w-lg px-4">
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Command palette"
              className="overflow-hidden rounded-xl border border-border bg-surface-elevated shadow-elevated"
            >
              <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                  className="h-4 w-4 shrink-0 text-ink-muted"
                >
                  <circle cx="11" cy="11" r="7" />
                  <path d="M21 21l-4.3-4.3" strokeLinecap="round" />
                </svg>
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActiveIndex(0);
                  }}
                  onKeyDown={onInputKeyDown}
                  placeholder="Type a page or action…"
                  aria-label="Search commands"
                  className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
                />
                <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[11px] text-ink-muted">
                  Esc
                </kbd>
              </div>

              <ul role="listbox" aria-label="Results" className="max-h-80 overflow-y-auto p-1.5">
                {filtered.length === 0 && (
                  <li className="px-3 py-6 text-center text-sm text-ink-muted">
                    Nothing matches &ldquo;{query}&rdquo;.
                  </li>
                )}
                {filtered.map((cmd, i) => (
                  <li key={cmd.id} role="option" aria-selected={i === activeIndex}>
                    <button
                      type="button"
                      onMouseEnter={() => setActiveIndex(i)}
                      onClick={() => activate(cmd)}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                        i === activeIndex
                          ? "bg-primary text-white"
                          : "text-ink-secondary hover:bg-page"
                      }`}
                    >
                      <cmd.icon className="h-4 w-4 shrink-0" />
                      {cmd.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
