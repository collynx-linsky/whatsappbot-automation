import Link from "next/link";

import { CONTACT_EMAIL, CONTACT_MAILTO } from "./constants";

export function MarketingFooter() {
  return (
    <footer className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="flex flex-col justify-between gap-8 sm:flex-row">
          <div className="max-w-xs">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                W
              </span>
              <span className="font-semibold text-zinc-900 dark:text-zinc-50">WABA AI</span>
            </div>
            <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
              A multi-tenant WhatsApp Business AI platform — one AI assistant, one inbox, one team,
              per business.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            <div>
              <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Product</p>
              <ul className="mt-3 space-y-2 text-sm text-zinc-500 dark:text-zinc-400">
                <li><a href="#features" className="hover:text-zinc-900 dark:hover:text-zinc-100">Features</a></li>
                <li><a href="#security" className="hover:text-zinc-900 dark:hover:text-zinc-100">Security</a></li>
                <li><a href="#pricing" className="hover:text-zinc-900 dark:hover:text-zinc-100">Pricing</a></li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Account</p>
              <ul className="mt-3 space-y-2 text-sm text-zinc-500 dark:text-zinc-400">
                <li><Link href="/login" className="hover:text-zinc-900 dark:hover:text-zinc-100">Log in</Link></li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Contact</p>
              <ul className="mt-3 space-y-2 text-sm text-zinc-500 dark:text-zinc-400">
                <li>
                  <a href={CONTACT_MAILTO} className="hover:text-zinc-900 dark:hover:text-zinc-100">
                    {CONTACT_EMAIL}
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-10 border-t border-zinc-100 pt-6 text-xs text-zinc-400 dark:border-zinc-900">
          © {new Date().getFullYear()} WABA AI. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
