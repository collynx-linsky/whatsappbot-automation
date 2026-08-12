import { expect, test } from "@playwright/test";

// Runs against the "authenticated" project's saved storageState (see
// playwright.config.ts / global-setup.ts) — a real session for the fixed
// E2E test user, obtained by actually driving the login+MFA UI once.
//
// The E2E Test Co tenant has no seeded conversations/products/customers,
// so most of these pages render an empty state, not populated data — that
// still proves the real thing: the page mounts, fetches from the real
// backend, and renders without crashing. Populated-data rendering (bar
// proportions, table rows) is Vitest's job with mocked data instead.

test.describe("Authenticated dashboard pages render without error", () => {
  test.beforeEach(async ({ page }) => {
    const pageErrors: Error[] = [];
    page.on("pageerror", (err) => pageErrors.push(err));
    // Attach the collector to the test so each `test(...)` body below can
    // assert on it after navigating.
    (test.info() as unknown as { pageErrors: Error[] }).pageErrors = pageErrors;
  });

  test.afterEach(async () => {
    const pageErrors = (test.info() as unknown as { pageErrors: Error[] }).pageErrors;
    expect(pageErrors, pageErrors.map((e) => e.message).join("\n")).toHaveLength(0);
  });

  test("Overview", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Business Dashboard" })).toBeVisible();
    await expect(page.getByText("E2E Test Co")).toBeVisible();
  });

  test("Products & Orders", async ({ page }) => {
    await page.goto("/dashboard/products");
    await expect(page.getByRole("heading", { name: "Products & Orders" })).toBeVisible();
    await expect(page.getByText("No products yet.")).toBeVisible();
  });

  test("Inbox", async ({ page }) => {
    await page.goto("/dashboard/inbox");
    await expect(page.getByRole("heading", { name: "Inbox" })).toBeVisible();
  });

  test("AI Assistant", async ({ page }) => {
    await page.goto("/dashboard/ai");
    await expect(page.getByRole("heading", { name: "AI Assistant" })).toBeVisible();
    // The E2E user is a business_owner, so the real settings form loads
    // (not the staff-only restricted notice) — proves the manager+ gate
    // and the real GET /api/v1/ai/settings/ round-trip both work.
    await expect(page.getByText("Test Your Assistant")).toBeVisible();
  });

  test("Knowledge Base", async ({ page }) => {
    await page.goto("/dashboard/knowledge");
    await expect(page.getByRole("heading", { name: "Knowledge Base" })).toBeVisible();
    await expect(page.getByText("No documents yet")).toBeVisible();
  });

  test("Campaigns", async ({ page }) => {
    await page.goto("/dashboard/campaigns");
    // level: 1 — the page also has a "Campaigns" section h2 lower down.
    await expect(page.getByRole("heading", { level: 1, name: "Campaigns" })).toBeVisible();
    await expect(page.getByText("No templates yet.")).toBeVisible();
  });

  test("WhatsApp", async ({ page }) => {
    await page.goto("/dashboard/whatsapp");
    await expect(page.getByRole("heading", { name: "WhatsApp" })).toBeVisible();
    // EmptyState's title/description split (see components/EmptyState.tsx).
    await expect(page.getByText("No WhatsApp number connected")).toBeVisible();
  });

  test("Billing", async ({ page }) => {
    await page.goto("/dashboard/billing");
    await expect(page.getByRole("heading", { name: "Billing" })).toBeVisible();
    await expect(page.getByText("Plan Usage")).toBeVisible();
  });

  test("Analytics", async ({ page }) => {
    await page.goto("/dashboard/analytics");
    await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
    await expect(page.getByText("Customer Funnel")).toBeVisible();
  });

  test("Sessions", async ({ page }) => {
    await page.goto("/dashboard/sessions");
    await expect(page.getByRole("heading", { name: "Active Sessions" })).toBeVisible();
  });

  test("logs out and lands back on the login page", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
