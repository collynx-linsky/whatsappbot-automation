import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sparkline } from "@/components/Sparkline";

describe("Sparkline", () => {
  it("shows an empty message when there is no data", () => {
    render(<Sparkline data={[]} />);
    expect(screen.getByText("No signups in this period.")).toBeInTheDocument();
  });

  it("renders an accessible summary and the date range caption", () => {
    render(
      <Sparkline
        data={[
          { date: "2026-07-12", count: 1 },
          { date: "2026-07-13", count: 0 },
          { date: "2026-07-14", count: 2 },
        ]}
      />,
    );
    expect(screen.getByRole("img", { name: "3 new tenants over the last 3 days" })).toBeInTheDocument();
    expect(screen.getByText(/2026-07-12/)).toBeInTheDocument();
    expect(screen.getByText(/2026-07-14/)).toBeInTheDocument();
  });

  it("uses singular phrasing for exactly one signup", () => {
    render(<Sparkline data={[{ date: "2026-07-12", count: 1 }]} />);
    expect(screen.getByRole("img", { name: "1 new tenant over the last 1 days" })).toBeInTheDocument();
  });
});
