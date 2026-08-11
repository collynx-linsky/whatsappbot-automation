import { CONTACT_MAILTO } from "./constants";
import { IconArrowRight } from "@/components/Icons";

// A hand-built illustrative chat mockup — not a screenshot of any real
// customer's conversation — demonstrating the actual hybrid AI/human
// behavior this platform runs (see apps.ai.services in the backend):
// the AI answers from the business's own knowledge base, and a real
// handoff to a human happens transparently when it should.
function ChatMockup() {
  return (
    <div className="w-full max-w-sm rounded-2xl border border-zinc-200 bg-white p-4 shadow-xl shadow-zinc-900/5 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-center gap-2 border-b border-zinc-100 pb-3 dark:border-zinc-800">
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Mambo Fashion — WhatsApp</p>
      </div>
      <div className="space-y-2.5">
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-zinc-100 px-3 py-2 text-sm text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
            Do you have the blue kitenge dress in size M?
          </div>
        </div>
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-emerald-600 px-3 py-2 text-sm text-white">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-emerald-100">
              AI Assistant
            </span>
            Yes! In stock — KES 3,200. Want me to place an order for you?
          </div>
        </div>
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-zinc-100 px-3 py-2 text-sm text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
            Can I get a discount for 3 dresses?
          </div>
        </div>
        <div className="flex justify-center">
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
            Handed off to Amina (Staff)
          </span>
        </div>
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-zinc-700 px-3 py-2 text-sm text-white dark:bg-zinc-600">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-zinc-300">
              Amina · Staff
            </span>
            Happy to help — 10% off for 3+ items. I&apos;ll send an order link now.
          </div>
        </div>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-zinc-50 dark:bg-zinc-950">
      <div
        aria-hidden
        className="absolute inset-x-0 -top-40 -z-10 flex justify-center blur-3xl"
      >
        <div className="h-80 w-[36rem] rounded-full bg-emerald-300/30 dark:bg-emerald-700/20" />
      </div>

      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 lg:grid-cols-2 lg:items-center lg:py-28">
        <div>
          <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
            WhatsApp Business, staffed by AI
          </span>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl dark:text-zinc-50">
            Every WhatsApp message answered.
            <br />
            <span className="text-emerald-600 dark:text-emerald-400">Instantly, or by the right person.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg text-zinc-600 dark:text-zinc-400">
            WABA AI runs a real AI assistant on your business&apos;s WhatsApp number — grounded in
            your own docs and catalog, never guessing at prices — and hands off to your team the
            moment a conversation actually needs a human. One inbox, full visibility, nothing
            dropped.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <a
              href={CONTACT_MAILTO}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-3 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700"
            >
              Get in touch
              <IconArrowRight />
            </a>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 px-5 py-3 text-sm font-medium text-zinc-700 transition-colors hover:bg-white dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
            >
              See how it works
            </a>
          </div>
          <p className="mt-6 text-xs text-zinc-500 dark:text-zinc-500">
            Multi-tenant · Mandatory two-factor auth · Full tenant data isolation
          </p>
        </div>

        <div className="flex justify-center lg:justify-end">
          <ChatMockup />
        </div>
      </div>
    </section>
  );
}
