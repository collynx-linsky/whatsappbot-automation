import {
  IconBook,
  IconCart,
  IconChart,
  IconChat,
  IconLayers,
  IconMegaphone,
  IconShield,
  IconSpark,
  IconUsers,
} from "@/components/Icons";

// Every card here describes something actually built and running in this
// codebase — see docs/ROADMAP.md for the phase each one shipped in. No
// vaporware on the marketing page.
const FEATURES = [
  {
    icon: IconSpark,
    title: "AI Assistant",
    body: "A hybrid AI-and-human assistant that replies on your business's own tone and rules — hand-off, human-only, or AI-only modes, with a configurable confidence threshold and keyword triggers.",
  },
  {
    icon: IconBook,
    title: "Knowledge Base",
    body: "Upload docs or paste text and the AI grounds every reply in your real catalog and policies — with an explicit instruction to never invent a price or a fact.",
  },
  {
    icon: IconChat,
    title: "Unified Inbox",
    body: "Every WhatsApp conversation in one place, assignable to a team member, with full history — nothing about a customer's context gets lost between AI and human replies.",
  },
  {
    icon: IconCart,
    title: "Products & Orders",
    body: "A real catalog with stock and pricing, and an order pipeline with an explicit confirm → process → deliver state machine — not a free-text status field.",
  },
  {
    icon: IconMegaphone,
    title: "Campaigns",
    body: "Segment your opted-in customers and send approved WhatsApp template messages — compliance is structural: a campaign can't reach anyone who hasn't opted in, full stop.",
  },
  {
    icon: IconChart,
    title: "Analytics",
    body: "Lead funnel, conversation and message volume, AI performance (replies vs. handoffs), real response-time measurement, and revenue — grouped honestly by currency, never summed across them.",
  },
  {
    icon: IconUsers,
    title: "Team & Roles",
    body: "Business Owner, Manager, and Staff roles with real server-side permission checks on every endpoint — invite your team and control exactly what each person can do.",
  },
  {
    icon: IconShield,
    title: "Security by default",
    body: "Mandatory two-factor authentication for every account, encrypted credentials at rest, and programmatically-audited tenant isolation — not a checkbox, an actual automated audit.",
  },
] as const;

export function FeatureGrid() {
  return (
    <section id="features" className="bg-white py-24 dark:bg-zinc-950">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            Everything your WhatsApp business needs, in one platform
          </h2>
          <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
            Not a chatbot bolted onto a spreadsheet — a full operating system for a WhatsApp-first
            business, from first message to paid invoice.
          </p>
        </div>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
                <f.icon />
              </div>
              <h3 className="mt-4 font-semibold text-zinc-900 dark:text-zinc-50">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{f.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-10 flex items-center justify-center gap-2 text-sm text-zinc-500 dark:text-zinc-500">
          <IconLayers className="h-4 w-4" />
          Every feature above ships together — no add-on modules, no separate contracts.
        </div>
      </div>
    </section>
  );
}
