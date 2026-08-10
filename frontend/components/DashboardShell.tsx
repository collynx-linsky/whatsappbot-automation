"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import * as api from "@/lib/api";
import type { User } from "@/types";

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

  async function handleLogout() {
    await api.logout();
    router.push("/login");
  }

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-zinc-950">
      <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">WABA AI</p>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{title}</h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right text-sm">
              <p className="font-medium text-zinc-900 dark:text-zinc-100">{user.full_name}</p>
              <p className="text-zinc-500 dark:text-zinc-400">
                {user.role.replace("_", " ")}
                {user.tenant_name ? ` · ${user.tenant_name}` : ""}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Log out
            </button>
          </div>
        </div>
        {nav && nav.length > 0 && (
          <nav className="mx-auto flex max-w-5xl gap-1 px-6">
            {nav.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? "border-emerald-600 text-emerald-600 dark:border-emerald-400 dark:text-emerald-400"
                      : "border-transparent text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        )}
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
