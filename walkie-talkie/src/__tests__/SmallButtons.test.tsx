import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SmallButtons from "../components/SmallButtons";

describe("SmallButtons", () => {
  it("renders the restart button", () => {
    render(<SmallButtons onRestart={vi.fn()} />);
    expect(screen.getByTestId("restart-button")).toBeInTheDocument();
  });

  it("calls onRestart when the restart button is clicked", () => {
    const onRestart = vi.fn();
    render(<SmallButtons onRestart={onRestart} />);
    fireEvent.click(screen.getByTestId("restart-button"));
    expect(onRestart).toHaveBeenCalledOnce();
  });

  it("restart button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} />);
    expect(screen.getByTestId("restart-button")).toHaveAttribute(
      "aria-label",
      "Restart session"
    );
  });

  it("renders the settings button when onSettings is provided", () => {
    render(<SmallButtons onRestart={vi.fn()} onSettings={vi.fn()} />);
    expect(screen.getByTestId("settings-button")).toBeInTheDocument();
  });

  it("calls onSettings when the settings button is clicked", () => {
    const onSettings = vi.fn();
    render(<SmallButtons onRestart={vi.fn()} onSettings={onSettings} />);
    fireEvent.click(screen.getByTestId("settings-button"));
    expect(onSettings).toHaveBeenCalledOnce();
  });

  it("settings button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} onSettings={vi.fn()} />);
    expect(screen.getByTestId("settings-button")).toHaveAttribute(
      "aria-label",
      "Settings"
    );
  });

  it("renders the home button when onHome is provided", () => {
    render(<SmallButtons onRestart={vi.fn()} onHome={vi.fn()} />);
    expect(screen.getByTestId("home-button")).toBeInTheDocument();
  });

  it("calls onHome when the home button is clicked", () => {
    const onHome = vi.fn();
    render(<SmallButtons onRestart={vi.fn()} onHome={onHome} />);
    fireEvent.click(screen.getByTestId("home-button"));
    expect(onHome).toHaveBeenCalledOnce();
  });

  it("home button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} onHome={vi.fn()} />);
    expect(screen.getByTestId("home-button")).toHaveAttribute(
      "aria-label",
      "Home"
    );
  });

  it("renders the cycle animation button when onCycleAnimation is provided", () => {
    render(<SmallButtons onRestart={vi.fn()} onCycleAnimation={vi.fn()} />);
    expect(screen.getByTestId("cycle-animation-button")).toBeInTheDocument();
  });

  it("calls onCycleAnimation when the cycle animation button is clicked", () => {
    const onCycle = vi.fn();
    render(<SmallButtons onRestart={vi.fn()} onCycleAnimation={onCycle} />);
    fireEvent.click(screen.getByTestId("cycle-animation-button"));
    expect(onCycle).toHaveBeenCalledOnce();
  });

  it("cycle animation button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} onCycleAnimation={vi.fn()} />);
    expect(screen.getByTestId("cycle-animation-button")).toHaveAttribute(
      "aria-label",
      "Cycle animation"
    );
  });

  it("renders exactly 4 disabled placeholder buttons (top row only)", () => {
    render(
      <SmallButtons
        onRestart={vi.fn()}
        onHome={vi.fn()}
        onCycleAnimation={vi.fn()}
        onSettings={vi.fn()}
      />
    );
    const disabled = screen
      .getAllByRole("button")
      .filter((btn) => btn.hasAttribute("disabled"));
    expect(disabled).toHaveLength(4);
  });

  it("does not call onRestart when a disabled placeholder is clicked", () => {
    const onRestart = vi.fn();
    render(<SmallButtons onRestart={onRestart} />);
    const placeholder = screen.getByLabelText("Function 1");
    fireEvent.click(placeholder);
    expect(onRestart).not.toHaveBeenCalled();
  });
});
