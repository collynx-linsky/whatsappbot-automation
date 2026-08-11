const STEPS = [
  {
    step: "01",
    title: "Connect your WhatsApp number",
    body: "Link your WhatsApp Business Cloud API number. Every inbound and outbound message flows through one verified, encrypted connection.",
  },
  {
    step: "02",
    title: "Train your assistant",
    body: "Upload your FAQs, catalog, and policies. Set the tone, the mode (AI-only, human-only, or hybrid), and the handoff rules — in plain settings, no prompt engineering required.",
  },
  {
    step: "03",
    title: "Let it run — with a safety net",
    body: "The AI answers what it's grounded to answer, and hands off transparently the moment a customer needs a real person, a refund, or anything outside its confidence threshold.",
  },
  {
    step: "04",
    title: "Watch it work",
    body: "See response times, AI-vs-human split, the lead funnel, and revenue in one dashboard — and adjust the rules any time as your business changes.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-zinc-50 py-24 dark:bg-zinc-900/40">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            Live in an afternoon, not a quarter
          </h2>
          <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
            Four steps, and your WhatsApp number is doing real work.
          </p>
        </div>

        <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <div key={s.step} className="relative">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-sm font-semibold text-white">
                  {s.step}
                </span>
                {i < STEPS.length - 1 && (
                  <span className="hidden h-px flex-1 bg-zinc-300 sm:block lg:hidden dark:bg-zinc-700" />
                )}
              </div>
              <h3 className="mt-4 font-semibold text-zinc-900 dark:text-zinc-50">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
