import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Meter } from "@/components/Meter";

describe("Meter", () => {
  it("prints used/limit and fills proportionally under the warning threshold", () => {
    render(<Meter label="Team members" used={2} limit={5} unlimited={false} />);
    expect(screen.getByText("Team members")).toBeInTheDocument();
    expect(screen.getByText("2 / 5")).toBeInTheDocument();
    expect(screen.getByTestId("meter-fill")).toHaveStyle({ width: "40%", backgroundColor: "#059669" });
  });

  it("turns amber between the warning and critical thresholds", () => {
    render(<Meter label="Customers" used={75} limit={100} unlimited={false} />);
    expect(screen.getByTestId("meter-fill")).toHaveStyle({ backgroundColor: "#d97706" });
  });

  it("turns red at or above the critical threshold", () => {
    render(<Meter label="AI messages" used={95} limit={100} unlimited={false} />);
    expect(screen.getByTestId("meter-fill")).toHaveStyle({ backgroundColor: "#dc2626" });
  });

  it("shows an Unlimited badge and no fill bar when unlimited", () => {
    render(<Meter label="Customers" used={500} limit={0} unlimited={true} />);
    expect(screen.getByText("Unlimited")).toBeInTheDocument();
    expect(screen.queryByTestId("meter-fill")).not.toBeInTheDocument();
  });

  it("clamps the fill width at 100% even if used exceeds limit", () => {
    render(<Meter label="Campaign sends" used={12} limit={10} unlimited={false} />);
    expect(screen.getByTestId("meter-fill")).toHaveStyle({ width: "100%" });
  });
});
