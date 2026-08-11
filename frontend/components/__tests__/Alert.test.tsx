import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Alert } from "@/components/Alert";

describe("Alert", () => {
  it("renders the message with an alert role", () => {
    render(<Alert kind="error" message="Something went wrong." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong.");
  });

  it("uses distinct styling for error vs. success", () => {
    const { rerender, container } = render(<Alert kind="error" message="Bad." />);
    const errorClasses = container.firstElementChild?.className ?? "";
    expect(errorClasses).toMatch(/red/);

    rerender(<Alert kind="success" message="Good." />);
    const successClasses = container.firstElementChild?.className ?? "";
    expect(successClasses).toMatch(/emerald/);
  });
});
