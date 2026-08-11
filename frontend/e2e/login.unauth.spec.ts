import { expect, test } from "@playwright/test";

// Deliberately runs with NO storageState (see playwright.config.ts's
// "unauthenticated" project) — these are the flows that only make sense
// without a session: the login form itself, and the client-side route
// guard every dashboard page relies on (see lib/useAuth.ts).
test.describe("Login and route guarding", () => {
  test("renders the login form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "WABA AI" })).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
  });

  test("shows a real error for wrong credentials, not a silent failure", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody@wabaai.local");
    await page.getByLabel("Password").fill("wrong-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 10_000 });
  });

  test("redirects an unauthenticated visitor away from a protected dashboard page", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("redirects an unauthenticated visitor away from the super-admin page", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe("Public marketing page", () => {
  test("renders for an anonymous visitor instead of bouncing to /login", async ({ page }) => {
    await page.goto("/");
    // The opposite of the dashboard/admin redirects above — "/" must stay
    // "/" for a visitor with no session, not redirect anywhere.
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: /Every WhatsApp message answered/ })).toBeVisible();
  });

  test("loads real, live pricing data from the backend", async ({ page }) => {
    await page.goto("/");
    // Confirms the public GET /api/v1/tenants/plans/public/ round-trip,
    // not just that the section renders — "Growth" and "$49" are real
    // seeded Plan data, not hardcoded copy (see apps.tenants.views
    // .PublicPlanListView).
    await expect(page.getByRole("heading", { name: "Growth" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("USD 49")).toBeVisible();
  });

  test("the mobile menu opens and links to Login", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByRole("button", { name: "Open menu" }).click();
    // Scoped to the header — the footer has its own "Log in" link too.
    await page.getByRole("banner").getByRole("link", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
