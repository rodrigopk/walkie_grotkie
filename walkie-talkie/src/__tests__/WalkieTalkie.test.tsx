import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import WalkieTalkie from "../components/WalkieTalkie";

describe("WalkieTalkie", () => {
  it("renders children inside the inner panel", () => {
    render(
      <WalkieTalkie>
        <div data-testid="child">Hello</div>
      </WalkieTalkie>
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("renders the speaker grille", () => {
    render(<WalkieTalkie><div /></WalkieTalkie>);
    expect(screen.getByTestId("device-speaker-grille")).toBeInTheDocument();
  });

  it("renders the OFF button when onQuit is provided", () => {
    render(<WalkieTalkie onQuit={vi.fn()}><div /></WalkieTalkie>);
    expect(screen.getByTestId("off-button")).toBeInTheDocument();
    expect(screen.getByTestId("off-button").querySelector("svg")).toBeTruthy();
  });

  it("calls onQuit when the OFF button is clicked", () => {
    const onQuit = vi.fn();
    render(<WalkieTalkie onQuit={onQuit}><div /></WalkieTalkie>);
    fireEvent.click(screen.getByTestId("off-button"));
    expect(onQuit).toHaveBeenCalledOnce();
  });

  it("OFF button has the correct aria-label", () => {
    render(<WalkieTalkie onQuit={vi.fn()}><div /></WalkieTalkie>);
    expect(screen.getByTestId("off-button")).toHaveAttribute(
      "aria-label",
      "Turn off"
    );
  });

  it("renders the walkie-talkie body", () => {
    render(<WalkieTalkie><div /></WalkieTalkie>);
    expect(screen.getByTestId("walkie-talkie-body")).toBeInTheDocument();
  });
});
