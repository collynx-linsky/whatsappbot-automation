import { CONTACT_MAILTO } from "./constants";
import { IconArrowRight } from "@/components/Icons";

export function FinalCTA() {
  return (
    <section className="bg-emerald-600">
      <div className="mx-auto max-w-4xl px-6 py-20 text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Ready to put AI to work on WhatsApp?
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-emerald-50">
          Tell us about your business and we&apos;ll get your WhatsApp number, your AI assistant,
          and your team set up.
        </p>
        <a
          href={CONTACT_MAILTO}
          className="mt-8 inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 text-sm font-semibold text-emerald-700 shadow-sm transition-colors hover:bg-emerald-50"
        >
          Get in touch
          <IconArrowRight />
        </a>
      </div>
    </section>
  );
}
