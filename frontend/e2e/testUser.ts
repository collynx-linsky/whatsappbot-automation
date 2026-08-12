// The fixed E2E test accounts Playwright logs in as. Dev/test-only, fixed,
// non-production credentials — the same "documented dev-only credential"
// pattern this project already uses for SUPERADMIN_EMAIL/PASSWORD (see
// README's "Default development credentials"), not a real secret.
//
// MUST match backend/apps/accounts/management/commands/provision_e2e_user.py
// exactly — that command is what actually creates these users (a business
// owner with a dedicated tenant, and a separate super admin, both MFA
// pre-enrolled against these same TOTP secrets) against the real dev
// database. Run it once (or whenever an account might have drifted) before
// running the e2e suite:
//   cd backend && .venv\Scripts\python.exe manage.py provision_e2e_user
export const E2E_EMAIL = "e2e-test@wabaai.local";
export const E2E_PASSWORD = "E2ETestPassword!2026";
export const E2E_TOTP_SECRET = "DPBG3PLCUTAXEA6KLNWPJP3QY4VFS3QF";

// Deliberately separate from the real SUPERADMIN_EMAIL account
// (createsuperadmin) — exists only so authenticated e2e/visual-QA coverage
// can reach /admin, which the business-owner account above correctly
// cannot (that's IsSuperAdmin working as intended).
export const E2E_ADMIN_EMAIL = "e2e-admin@wabaai.local";
export const E2E_ADMIN_PASSWORD = "E2EAdminPassword!2026";
export const E2E_ADMIN_TOTP_SECRET = "JJLFDUPIC5LS3D3MAJPCWEQKEMBS3FEF";
