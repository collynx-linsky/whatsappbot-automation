// This platform's onboarding is admin-driven, not public self-serve (see
// README — a super admin onboards each new business via /admin) — so the
// marketing site's CTA is honestly "get in touch," never a signup form
// that would pretend to create an account on submit. `.example` is the
// IANA-reserved documentation domain — the correct choice for illustrative
// contact info, not a real inbox.
export const CONTACT_EMAIL = "hello@wabaai.example";
export const CONTACT_MAILTO = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Interested in WABA AI")}`;
