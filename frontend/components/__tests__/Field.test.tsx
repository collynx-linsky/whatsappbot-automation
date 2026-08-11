import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field } from "@/components/Field";

describe("Field", () => {
  it("renders the label and current value", () => {
    render(<Field label="Email" value="a@b.com" onChange={() => {}} />);
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByDisplayValue("a@b.com")).toBeInTheDocument();
  });

  it("calls onChange with the typed character", async () => {
    const onChange = vi.fn();
    // `value` is a static prop here (not wired to state), so the input
    // stays controlled-empty across keystrokes — each keystroke's change
    // event reports just that one character, not an accumulated string.
    render(<Field label="Name" value="" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText("Name"), "x");
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("x");
  });

  it("marks the input required when asked", () => {
    render(<Field label="Email" value="" onChange={() => {}} required />);
    expect(screen.getByLabelText("Email")).toBeRequired();
  });
});
