import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SmallButtons from "../components/SmallButtons";

describe("SmallButtons", () => {
  it("renders the quit button", () => {
    render(<SmallButtons onQuit={vi.fn()} />);
    expect(screen.getByTestId("quit-button")).toBeInTheDocument();
  });

  it("calls onQuit when the quit button is clicked", () => {
    const onQuit = vi.fn();
    render(<SmallButtons onQuit={onQuit} />);
    fireEvent.click(screen.getByTestId("quit-button"));
    expect(onQuit).toHaveBeenCalledOnce();
  });

  it("renders the settings button when onSettings is provided", () => {
    render(<SmallButtons onQuit={vi.fn()} onSettings={vi.fn()} />);
    expect(screen.getByTestId("settings-button")).toBeInTheDocument();
  });

  it("calls onSettings when the settings button is clicked", () => {
    const onSettings = vi.fn();
    render(<SmallButtons onQuit={vi.fn()} onSettings={onSettings} />);
    fireEvent.click(screen.getByTestId("settings-button"));
    expect(onSettings).toHaveBeenCalledOnce();
  });

  it("settings button has the correct aria-label", () => {
    render(<SmallButtons onQuit={vi.fn()} onSettings={vi.fn()} />);
    expect(screen.getByTestId("settings-button")).toHaveAttribute(
      "aria-label",
      "Settings"
    );
  });

  it("quit button has the correct aria-label", () => {
    render(<SmallButtons onQuit={vi.fn()} />);
    expect(screen.getByTestId("quit-button")).toHaveAttribute(
      "aria-label",
      "Quit application"
    );
  });

  it("renders disabled placeholder buttons", () => {
    render(<SmallButtons onQuit={vi.fn()} />);
    const disabled = screen
      .getAllByRole("button")
      .filter((btn) => btn.hasAttribute("disabled"));
    expect(disabled.length).toBeGreaterThanOrEqual(6);
  });

  it("does not call onQuit when a disabled placeholder is clicked", () => {
    const onQuit = vi.fn();
    render(<SmallButtons onQuit={onQuit} />);
    const placeholder = screen.getByLabelText("Function 1");
    fireEvent.click(placeholder);
    expect(onQuit).not.toHaveBeenCalled();
  });
});
