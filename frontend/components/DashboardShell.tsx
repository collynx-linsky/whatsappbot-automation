"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ComponentType, type ReactNode, useState } from "react";

import {
  IconBook,
  IconCart,
  IconChart,
  IconChat,
  IconCreditCard,
  IconHome,
  IconLayers,
  IconLogout,
  IconMegaphone,
  IconMenu,
  IconPhone,
  IconShield,
  IconSpark,
} from "@/components/Icons";
import * as api from "@/lib/api";
import type { User } from "@/types";

// Keyed by href so every dashboard page's existing `nav` prop (just
// {label, href} pairs) picks up an icon automatically — no page needs to
// change to get one. Falls back to IconLayers for any href not listed
// here (e.g. a future page) rather than rendering nothing.
const NAV_ICON: Record<string, ComponentType<{ className?: string }>> = {
  "/dashboard": IconHome,
  "/dashboard/products": IconCart,
  "/dashboard/inbox": IconChat,
  "/dashboard/ai": IconSpark,
  "/dashboard/knowledge": IconBook,
  "/dashboard/campaigns": IconMegaphone,
  "/dashboard/whatsapp": IconPhone,
  "/dashboard/billing": IconCreditCard,
  "/dashboard/analytics": IconChart,
};

function initials(name: string): string {
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
  nav?: { label: string; href: string }[];
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
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
          W
        </span>
        <span className="text-base font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          WABA AI
        </span>
      </Link>

      {nav && nav.length > 0 && (
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
          {nav.map((item) => {
            const Icon = NAV_ICON[item.href] ?? IconLayers;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`}
              >
                <Icon className="h-[18px] w-[18px] shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      )}

      <div className="mt-auto border-t border-zinc-100 p-3 dark:border-zinc-800">
        <Link
          href="/dashboard/sessions"
          onClick={() => setMobileOpen(false)}
          className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
            pathname === "/dashboard/sessions"
              ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
              : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          }`}
        >
          <IconShield className="h-[18px] w-[18px] shrink-0" />
          Sessions
        </Link>

        <div className="mt-2 flex items-center gap-2.5 rounded-lg px-3 py-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-200 text-xs font-semibold text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200">
            {initials(user.full_name) || "?"}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
              {user.full_name}
            </p>
            <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
              {user.role.replace("_", " ")}
              {user.tenant_name ? ` · ${user.tenant_name}` : ""}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Log out"
            aria-label="Log out"
            className="shrink-0 rounded-lg p-1.5 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
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
      <aside className="hidden w-64 shrink-0 border-r border-zinc-200 bg-white lg:block dark:border-zinc-800 dark:bg-zinc-900">
        {sidebar}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar — the sidebar becomes a slide-out drawer below lg. */}
        <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-3 lg:hidden dark:border-zinc-800 dark:bg-zinc-900">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-2 text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <IconMenu />
          </button>
          <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{title}</span>
          <span className="w-9" aria-hidden />
        </header>

        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="absolute inset-0 bg-zinc-900/40"
              onClick={() => setMobileOpen(false)}
              aria-hidden
            />
            <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
              {sidebar}
            </div>
          </div>
        )}

        {/* Desktop page header. */}
        <div className="hidden border-b border-zinc-200 bg-white px-8 py-5 lg:block dark:border-zinc-800 dark:bg-zinc-900">
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{title}</h1>
        </div>

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>

        <footer className="border-t border-zinc-200 bg-white px-4 py-4 sm:px-6 lg:px-8 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-2 text-xs text-zinc-400 sm:flex-row dark:text-zinc-500">
            <span>© {new Date().getFullYear()} WABA AI. All rights reserved.</span>
            <Link href="/" className="hover:text-zinc-600 dark:hover:text-zinc-300">
              Back to homepage
            </Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
