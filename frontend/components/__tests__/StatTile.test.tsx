import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatTile } from "@/components/StatTile";

describe("StatTile", () => {
  it("renders the label and value", () => {
    render(<StatTile label="Conversations" value="42" />);
    expect(screen.getByText("Conversations")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("renders an optional hint, and omits it when not given", () => {
    const { rerender } = render(<StatTile label="Response Time" value="1.2m" hint="from 8 replies" />);
    expect(screen.getByText("from 8 replies")).toBeInTheDocument();

    rerender(<StatTile label="Response Time" value="1.2m" />);
    expect(screen.queryByText("from 8 replies")).not.toBeInTheDocument();
  });
});
