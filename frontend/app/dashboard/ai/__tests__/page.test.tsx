import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AISettings, User } from "@/types";

const { getAISettings } = vi.hoisted(() => ({ getAISettings: vi.fn() }));

vi.mock("@/lib/api", () => ({
  getAISettings,
  updateAISettings: vi.fn(),
  testAI: vi.fn(),
  logout: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard/ai",
}));

const baseUser: User = {
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

const settings: AISettings = {
  id: "s1",
  tenant: "t1",
  business: "b1",
  assistant_name: "Test Assistant",
  system_prompt: "",
  language: "en",
  tone: "friendly",
  welcome_message: "Hi there!",
  fallback_message: "Let me get a human.",
  max_response_length: 500,
  mode: "hybrid",
  ai_enabled: true,
  human_handoff_enabled: true,
  confidence_threshold: 0.6,
  handoff_keywords: ["refund", "human"],
  provider: "openai",
  model_name: "",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// Imported after the mocks above so the mocked modules are already
// registered by the time the page module (and its DashboardShell import)
// resolves them.
async function renderPageAs(role: User["role"]) {
  vi.doMock("@/lib/useAuth", () => ({
    useRequireAuth: () => ({ user: { ...baseUser, role }, ready: true }),
  }));
  const { default: AISettingsPage } = await import("../page");
  render(<AISettingsPage />);
}

describe("AI settings page — role gating", () => {
  beforeEach(() => {
    vi.resetModules();
    getAISettings.mockReset();
    getAISettings.mockResolvedValue(settings);
  });

  it("shows a restricted notice to staff and never fetches settings", async () => {
    await renderPageAs("staff");
    expect(
      screen.getByText(/only available to business owners and managers/i),
    ).toBeInTheDocument();
    expect(getAISettings).not.toHaveBeenCalled();
  });

  it("loads and displays the real settings for a business owner", async () => {
    await renderPageAs("business_owner");
    await waitFor(() => expect(getAISettings).toHaveBeenCalledTimes(1));
    expect(await screen.findByDisplayValue("Test Assistant")).toBeInTheDocument();
    expect(screen.getByText("Test Your Assistant")).toBeInTheDocument();
  });

  it("loads settings for a manager too", async () => {
    await renderPageAs("manager");
    await waitFor(() => expect(getAISettings).toHaveBeenCalledTimes(1));
    expect(await screen.findByDisplayValue("Test Assistant")).toBeInTheDocument();
  });
});
