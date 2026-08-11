"use client";

import { useEffect, useState } from "react";

import { ApiError, getPublicPlans } from "@/lib/api";
import type { PublicPlan } from "@/types";
import { CONTACT_MAILTO } from "./constants";
import { IconCheck } from "@/components/Icons";

function formatPrice(plan: PublicPlan): string {
  const amount = Number(plan.price_monthly);
  if (amount === 0) return "Free";
  return `${plan.currency} ${amount.toLocaleString()}`;
}

function planLimitLines(plan: PublicPlan): string[] {
  const unlimited = (n: number) => (n === 0 ? "Unlimited" : n.toLocaleString());
  return [
    `${unlimited(plan.max_users)} team members`,
    `${unlimited(plan.max_whatsapp_accounts)} WhatsApp number${plan.max_whatsapp_accounts === 1 ? "" : "s"}`,
    `${unlimited(plan.max_ai_messages_per_month)} AI messages / month`,
    `${unlimited(plan.max_customers)} customers`,
    `${unlimited(plan.max_campaigns_per_month)} campaign sends / month`,
  ];
}

export function Pricing() {
  const [plans, setPlans] = useState<PublicPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPublicPlans()
      .then((res) => setPlans(res.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load plans."));
  }, []);

  return (
    <section id="pricing" className="bg-zinc-50 py-24 dark:bg-zinc-900/40">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            Simple, honest pricing
          </h2>
          <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
            Real plans, pulled live from the platform — not marketing copy that drifts from what
            you actually get.
          </p>
        </div>

        {error && (
          <p className="mx-auto mt-10 max-w-md text-center text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        <div className="mx-auto mt-14 grid max-w-5xl gap-6 lg:grid-cols-3">
          {plans === null && !error && (
            <p className="col-span-3 text-center text-sm text-zinc-500">Loading plans…</p>
          )}

          {plans?.map((plan, i) => {
            const featured = i === plans.length - 1 && plans.length > 1;
            return (
              <div
                key={plan.id}
                className={`rounded-2xl border p-8 ${
                  featured
                    ? "border-emerald-600 bg-white shadow-lg ring-1 ring-emerald-600 dark:bg-zinc-900"
                    : "border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
                }`}
              >
                {featured && (
                  <span className="mb-3 inline-block rounded-full bg-emerald-600 px-2.5 py-0.5 text-xs font-medium text-white">
                    Most popular
                  </span>
                )}
                <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{plan.name}</h3>
                {plan.description && (
                  <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{plan.description}</p>
                )}
                <p className="mt-4 text-3xl font-semibold text-zinc-900 dark:text-zinc-50">
                  {formatPrice(plan)}
                  {Number(plan.price_monthly) > 0 && (
                    <span className="text-base font-normal text-zinc-500 dark:text-zinc-400">/mo</span>
                  )}
                </p>
                <ul className="mt-6 space-y-2.5">
                  {planLimitLines(plan).map((line) => (
                    <li key={line} className="flex items-start gap-2.5 text-sm text-zinc-700 dark:text-zinc-300">
                      <IconCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                      {line}
                    </li>
                  ))}
                </ul>
                <a
                  href={CONTACT_MAILTO}
                  className={`mt-8 block rounded-lg px-4 py-2.5 text-center text-sm font-medium transition-colors ${
                    featured
                      ? "bg-emerald-600 text-white hover:bg-emerald-700"
                      : "border border-zinc-300 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                  }`}
                >
                  Get in touch
                </a>
              </div>
            );
          })}

          <div className="rounded-2xl border border-dashed border-zinc-300 bg-white p-8 dark:border-zinc-700 dark:bg-zinc-900">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Enterprise</h3>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Higher volume, custom limits, or dedicated support.
            </p>
            <p className="mt-4 text-3xl font-semibold text-zinc-900 dark:text-zinc-50">Custom</p>
            <ul className="mt-6 space-y-2.5">
              {["Everything in Growth", "Custom usage limits", "Priority support"].map((line) => (
                <li key={line} className="flex items-start gap-2.5 text-sm text-zinc-700 dark:text-zinc-300">
                  <IconCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  {line}
                </li>
              ))}
            </ul>
            <a
              href={CONTACT_MAILTO}
              className="mt-8 block rounded-lg border border-zinc-300 px-4 py-2.5 text-center text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Talk to us
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
