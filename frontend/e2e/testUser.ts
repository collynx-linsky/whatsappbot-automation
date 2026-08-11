// The fixed E2E test account Playwright logs in as. Dev/test-only, fixed,
// non-production credentials — the same "documented dev-only credential"
// pattern this project already uses for SUPERADMIN_EMAIL/PASSWORD (see
// README's "Default development credentials"), not a real secret.
//
// MUST match backend/apps/accounts/management/commands/provision_e2e_user.py
// exactly — that command is what actually creates this user (dedicated
// tenant, MFA pre-enrolled against this same TOTP secret) against the real
// dev database. Run it once (or whenever the account might have drifted)
// before running the e2e suite:
//   cd backend && .venv\Scripts\python.exe manage.py provision_e2e_user
export const E2E_EMAIL = "e2e-test@wabaai.local";
export const E2E_PASSWORD = "E2ETestPassword!2026";
export const E2E_TOTP_SECRET = "DPBG3PLCUTAXEA6KLNWPJP3QY4VFS3QF";
