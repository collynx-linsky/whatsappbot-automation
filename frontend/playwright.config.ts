import { defineConfig, devices } from "@playwright/test";

// Real end-to-end coverage — a real Chromium browser driving the real
// running Next.js app against the real running Django backend. This is
// the layer that closes the "never actually clicked through" gap every
// frontend session in docs/ROADMAP.md has flagged; Vitest (vitest.config.ts)
// covers fast component-level logic instead. See docs/testing.md.
//
// Requires the backend (`manage.py runserver`) to be running separately
// with a seeded database AND the fixed E2E test user provisioned once via
// `manage.py provision_e2e_user` (see e2e/testUser.ts) — Playwright starts
// the frontend dev server for you (or reuses one already running) but has
// no way to start Django, matching this project's existing hybrid
// dev-setup convention (see docs/development.md).
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "unauthenticated",
      testMatch: /.*\.unauth\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "authenticated",
      testMatch: /.*\.spec\.ts/,
      testIgnore: /.*\.unauth\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], storageState: "e2e/.auth/user.json" },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
