import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BarList, BarListLegend } from "@/components/BarList";

describe("BarList", () => {
  it("shows the empty label when there are no items", () => {
    render(<BarList items={[]} emptyLabel="Nothing to see here." />);
    expect(screen.getByText("Nothing to see here.")).toBeInTheDocument();
  });

  it("shows the empty label when every item is zero", () => {
    render(
      <BarList
        items={[
          { key: "a", label: "A", value: 0 },
          { key: "b", label: "B", value: 0 },
        ]}
        emptyLabel="No data yet."
      />,
    );
    expect(screen.getByText("No data yet.")).toBeInTheDocument();
  });

  it("renders one row per item with its label and formatted value", () => {
    render(
      <BarList
        items={[
          { key: "open", label: "Open", value: 4 },
          { key: "closed", label: "Closed", value: 2 },
        ]}
        valueFormat={(v) => `${v} items`}
      />,
    );
    expect(screen.getByText("Open")).toBeInTheDocument();
    expect(screen.getByText("4 items")).toBeInTheDocument();
    expect(screen.getByText("Closed")).toBeInTheDocument();
    expect(screen.getByText("2 items")).toBeInTheDocument();
  });

  it("sizes the largest bar's fill at 100% and scales the rest against it", () => {
    const { container } = render(
      <BarList
        items={[
          { key: "big", label: "Big", value: 10 },
          { key: "small", label: "Small", value: 5 },
        ]}
      />,
    );
    const fills = container.querySelectorAll("li span > span");
    expect(fills[0]).toHaveStyle({ width: "100%" });
    expect(fills[1]).toHaveStyle({ width: "50%" });
  });

  it("uses a per-item color when provided, falling back to the default otherwise", () => {
    const { container } = render(
      <BarList
        items={[
          { key: "custom", label: "Custom", value: 1, color: "#3b82f6" },
          { key: "default", label: "Default", value: 1 },
        ]}
      />,
    );
    const fills = container.querySelectorAll("li span > span");
    expect(fills[0]).toHaveStyle({ backgroundColor: "rgb(59, 130, 246)" });
    expect(fills[1]).toHaveStyle({ backgroundColor: "#059669" });
  });
});

describe("BarListLegend", () => {
  it("renders a swatch and label per entry", () => {
    render(
      <BarListLegend
        items={[
          { key: "a", label: "Customer", color: "#3b82f6" },
          { key: "b", label: "Staff", color: "#059669" },
        ]}
      />,
    );
    expect(screen.getByText("Customer")).toBeInTheDocument();
    expect(screen.getByText("Staff")).toBeInTheDocument();
  });
});
