import { chromium, expect } from "@playwright/test";
import * as OTPAuth from "otpauth";

import { E2E_EMAIL, E2E_PASSWORD, E2E_TOTP_SECRET } from "./testUser";

// Drives the real /login -> /login/mfa-verify UI flow once (not a shortcut
// through localStorage) so the login+MFA contract itself is exercised, then
// saves the resulting session (localStorage, since this app has no
// server-side cookie session — see lib/auth.ts) for every "authenticated"
// test to reuse without re-logging-in per spec.
export default async function globalSetup() {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto("http://localhost:3000/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/login\/mfa-verify/, { timeout: 15_000 });

  const totp = new OTPAuth.TOTP({
    secret: OTPAuth.Secret.fromBase32(E2E_TOTP_SECRET),
    digits: 6,
    period: 30,
    algorithm: "SHA1",
  });
  await page.getByLabel("6-digit code").fill(totp.generate());
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
  // Confirm a real session actually landed, not just a URL that happens to
  // match mid-navigation — "E2E Test" is provision_e2e_user's fixed name.
  // Exact match: "E2E Test Co" (the tenant name, shown just below) also
  // contains this substring.
  await expect(page.getByText("E2E Test", { exact: true })).toBeVisible();

  await page.context().storageState({ path: "e2e/.auth/user.json" });
  await browser.close();
}
