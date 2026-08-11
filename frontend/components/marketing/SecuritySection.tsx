import { IconCheck, IconLock, IconShield, IconUsers } from "@/components/Icons";

// Every line item here is a real, built, tested control — cross-check
// against docs/security.md and docs/mfa.md. Nothing aspirational.
const CONTROLS = [
  "Mandatory two-factor authentication (TOTP) for every account, every role — including platform admins, no exceptions",
  "Every business's data is fully isolated — proven by an automated, re-runnable tenant-isolation audit, not just code review",
  "Access tokens and other secrets are encrypted at rest and never returned by any API response",
  "Every sensitive action is written to an audit log: who, what, when",
  "Rate limiting on every write-heavy and cost-sensitive endpoint",
  "Account lockout after repeated failed logins, with session visibility and one-click revocation",
];

export function SecuritySection() {
  return (
    <section id="security" className="bg-white py-24 dark:bg-zinc-950">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 lg:grid-cols-2 lg:items-center">
        <div>
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
            <IconShield className="h-6 w-6" />
          </div>
          <h2 className="mt-5 text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            Built for businesses that can&apos;t afford a data leak
          </h2>
          <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
            Every business on the platform is a separate company with its own customers and its
            own conversations. Isolation between them isn&apos;t a policy — it&apos;s enforced in
            code and checked automatically.
          </p>

          <ul className="mt-8 space-y-3">
            {CONTROLS.map((c) => (
              <li key={c} className="flex items-start gap-3 text-sm text-zinc-700 dark:text-zinc-300">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400">
                  <IconCheck className="h-3.5 w-3.5" />
                </span>
                {c}
              </li>
            ))}
          </ul>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <IconLock className="h-7 w-7 text-emerald-600 dark:text-emerald-400" />
            <p className="mt-3 font-semibold text-zinc-900 dark:text-zinc-50">Encrypted at rest</p>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              WhatsApp tokens and MFA secrets are never stored in plain text.
            </p>
          </div>
          <div className="rounded-2xl border border-zinc-200 bg-zinc-50 p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <IconUsers className="h-7 w-7 text-emerald-600 dark:text-emerald-400" />
            <p className="mt-3 font-semibold text-zinc-900 dark:text-zinc-50">Role-based access</p>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Owner, Manager, and Staff — enforced server-side on every request.
            </p>
          </div>
          <div className="col-span-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-6 dark:border-emerald-900/50 dark:bg-emerald-950/30">
            <p className="font-semibold text-emerald-900 dark:text-emerald-200">
              Tenant isolation, audited — not assumed
            </p>
            <p className="mt-1 text-sm text-emerald-800/80 dark:text-emerald-300/80">
              A programmatic audit walks every API endpoint on every build and confirms it
              filters by tenant correctly — a regression here fails the build, it doesn&apos;t
              ship.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
