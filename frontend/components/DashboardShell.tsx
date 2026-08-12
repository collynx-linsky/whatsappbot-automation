"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

import { CommandPalette } from "@/components/CommandPalette";
import { IconLogout, IconMenu, IconShield } from "@/components/Icons";
import * as api from "@/lib/api";
import type { NavItem } from "@/lib/navigation";
import type { User } from "@/types";

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return (parts[0]?.[0] ?? "") + (parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "");
}

export function DashboardShell({
  user,
  title,
  nav,
  children,
}: {
  user: User;
  title: string;
  // Callers pass lib/navigation.ts's DASHBOARD_NAV (the one canonical
  // list) — /admin passes nothing, since the super-admin surface is a
  // separate single-route surface, not a tenant-side module.
  nav?: NavItem[];
  children: ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await api.logout();
    router.push("/login");
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <Link href="/" className="flex items-center gap-2 px-5 py-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
          W
        </span>
        <span className="text-base font-semibold tracking-tight text-ink">WABA AI</span>
      </Link>

      {nav && nav.length > 0 && (
        <nav aria-label="Primary" className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {nav.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-success-surface text-primary"
                    : "text-ink-muted hover:bg-page hover:text-ink-secondary"
                }`}
              >
                <item.icon className="h-[18px] w-[18px] shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      )}

      <div className="mt-auto border-t border-divider p-3">
        <Link
          href="/dashboard/sessions"
          onClick={() => setMobileOpen(false)}
          aria-current={pathname === "/dashboard/sessions" ? "page" : undefined}
          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
            pathname === "/dashboard/sessions"
              ? "bg-success-surface text-primary"
              : "text-ink-muted hover:bg-page hover:text-ink-secondary"
          }`}
        >
          <IconShield className="h-[18px] w-[18px] shrink-0" />
          Sessions
        </Link>

        <div className="mt-2 flex items-center gap-2.5 rounded-lg px-3 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-page text-xs font-semibold text-ink-secondary">
            {initials(user.full_name) || "?"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
            <p className="truncate text-xs text-ink-muted">
              {user.role.replace("_", " ")}
              {user.tenant_name ? ` · ${user.tenant_name}` : ""}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Log out"
            aria-label="Log out"
            className="shrink-0 rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-page hover:text-ink-secondary"
          >
            <IconLogout />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-full flex-1">
      {/* Desktop sidebar — always visible at lg+, matching the app's
          existing lg-first responsive convention elsewhere. */}
      <aside className="hidden w-64 shrink-0 border-r border-border bg-surface lg:block">{sidebar}</aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar — the sidebar becomes a slide-out drawer below lg. */}
        <header className="flex items-center justify-between border-b border-border bg-surface px-4 py-3 lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 text-ink-secondary hover:bg-page"
          >
            <IconMenu />
          </button>
          <span className="text-sm font-semibold text-ink">{title}</span>
          <span className="w-9" aria-hidden />
        </header>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-zinc-900/40" onClick={() => setMobileOpen(false)} aria-hidden />
            <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-surface shadow-elevated">
              {sidebar}
            </div>
          </div>
        )}

        {/* Desktop page header. */}
        <div className="hidden items-center justify-between gap-6 border-b border-border bg-surface px-8 py-5 lg:flex">
          <h1 className="text-xl font-semibold text-ink">{title}</h1>
          <CommandPalette onLogout={handleLogout} />
        </div>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>

        <footer className="border-t border-border bg-surface px-4 py-4 sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-2 text-xs text-ink-muted sm:flex-row">
            <span>© {new Date().getFullYear()} WABA AI. All rights reserved.</span>
            <Link href="/" className="hover:text-ink-secondary">
              Back to homepage
            </Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
