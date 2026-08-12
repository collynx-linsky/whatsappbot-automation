import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardShell, initials } from "@/components/DashboardShell";
import { DASHBOARD_NAV } from "@/lib/navigation";
import type { User } from "@/types";

const { logout, push } = vi.hoisted(() => ({
  logout: vi.fn().mockResolvedValue(undefined),
  push: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ logout }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/dashboard/analytics",
}));

const user: User = {
  id: "u1",
  email: "owner@test.local",
  phone: "",
  first_name: "Jane",
  last_name: "Doe",
  full_name: "Jane Doe",
  role: "business_owner",
  tenant_id: "t1",
  tenant_name: "Test Co",
  is_active: true,
  date_joined: "2026-01-01T00:00:00Z",
};

describe("initials()", () => {
  it("uses first+last initial for a multi-word name", () => {
    expect(initials("Jane Doe")).toBe("JD");
  });

  it("uses first+last initial across more than two words (first and last only)", () => {
    expect(initials("Jane Middle Doe")).toBe("JD");
  });

  it("uses just the first initial for a one-word name", () => {
    expect(initials("Madonna")).toBe("M");
  });

  it("returns an empty string for an empty name (caller falls back to '?')", () => {
    expect(initials("")).toBe("");
    expect(initials("   ")).toBe("");
  });
});

describe("DashboardShell", () => {
  beforeEach(() => {
    logout.mockClear();
    push.mockClear();
  });

  it("renders every canonical nav item as a link to its real route", () => {
    render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    for (const item of DASHBOARD_NAV) {
      const links = screen.getAllByRole("link", { name: new RegExp(item.label) });
      expect(links.some((l) => l.getAttribute("href") === item.href)).toBe(true);
    }
  });

  it("marks the current route's nav link as the active page", () => {
    render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    // usePathname is mocked to "/dashboard/analytics" — Analytics is current.
    const analyticsLinks = screen.getAllByRole("link", { name: "Analytics" });
    expect(analyticsLinks.some((l) => l.getAttribute("aria-current") === "page")).toBe(true);
    const productsLinks = screen.getAllByRole("link", { name: /Products/ });
    expect(productsLinks.every((l) => l.getAttribute("aria-current") !== "page")).toBe(true);
  });

  it("renders no nav section when nav is omitted (the /admin usage)", () => {
    render(
      <DashboardShell user={user} title="Platform — Super Admin">
        <p>content</p>
      </DashboardShell>,
    );
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("shows the user's name, role, and tenant", () => {
    render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    expect(screen.getAllByText("Jane Doe").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/business owner/).length).toBeGreaterThan(0);
  });

  it("logs out and redirects to /login", async () => {
    render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    await userEvent.click(screen.getAllByRole("button", { name: "Log out" })[0]);
    expect(logout).toHaveBeenCalledTimes(1);
    expect(push).toHaveBeenCalledWith("/login");
  });

  it("opens the mobile drawer, then closes it when a nav link is clicked", async () => {
    render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    // Only one "Open menu" trigger exists — the mobile top bar's hamburger.
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    // Once open, the nav items are duplicated (desktop sidebar + drawer) —
    // there should now be two link sets for the same route.
    const inboxLinksOpen = screen.getAllByRole("link", { name: "Inbox" });
    expect(inboxLinksOpen.length).toBeGreaterThanOrEqual(2);

    await userEvent.click(inboxLinksOpen[inboxLinksOpen.length - 1]);
    // Closing the drawer removes its duplicate copy of the nav.
    const inboxLinksClosed = screen.getAllByRole("link", { name: "Inbox" });
    expect(inboxLinksClosed.length).toBe(1);
  });

  it("closes the mobile drawer when the backdrop is clicked", async () => {
    const { container } = render(
      <DashboardShell user={user} title="Analytics" nav={DASHBOARD_NAV}>
        <p>content</p>
      </DashboardShell>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getAllByRole("link", { name: "Inbox" }).length).toBeGreaterThanOrEqual(2);

    const backdrop = container.querySelector('[aria-hidden="true"].bg-zinc-900\\/40');
    expect(backdrop).not.toBeNull();
    await userEvent.click(backdrop as Element);
    expect(screen.getAllByRole("link", { name: "Inbox" }).length).toBe(1);
  });
});
