import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SmallButtons from "../components/SmallButtons";

describe("SmallButtons", () => {
  // ── Restart ──────────────────────────────────────────────────
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

  // ── Settings ─────────────────────────────────────────────────
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

  // ── Home ─────────────────────────────────────────────────────
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

  // ── Cycle animation ───────────────────────────────────────────
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

  // ── Help ──────────────────────────────────────────────────────
  it("renders the help button when onHelp is provided", () => {
    render(<SmallButtons onRestart={vi.fn()} onHelp={vi.fn()} />);
    expect(screen.getByTestId("help-button")).toBeInTheDocument();
  });

  it("calls onHelp when the help button is clicked", () => {
    const onHelp = vi.fn();
    render(<SmallButtons onRestart={vi.fn()} onHelp={onHelp} />);
    fireEvent.click(screen.getByTestId("help-button"));
    expect(onHelp).toHaveBeenCalledOnce();
  });

  it("help button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} onHelp={vi.fn()} />);
    expect(screen.getByTestId("help-button")).toHaveAttribute(
      "aria-label",
      "Help"
    );
  });

  // ── Voice ─────────────────────────────────────────────────────
  it("renders the voice button when onVoice is provided", () => {
    render(<SmallButtons onRestart={vi.fn()} onVoice={vi.fn()} />);
    expect(screen.getByTestId("voice-button")).toBeInTheDocument();
  });

  it("calls onVoice when the voice button is clicked", () => {
    const onVoice = vi.fn();
    render(<SmallButtons onRestart={vi.fn()} onVoice={onVoice} />);
    fireEvent.click(screen.getByTestId("voice-button"));
    expect(onVoice).toHaveBeenCalledOnce();
  });

  it("voice button has the correct aria-label", () => {
    render(<SmallButtons onRestart={vi.fn()} onVoice={vi.fn()} />);
    expect(screen.getByTestId("voice-button")).toHaveAttribute(
      "aria-label",
      "Voice"
    );
  });

  // ── Layout ────────────────────────────────────────────────────
  it("renders exactly 6 buttons total", () => {
    render(
      <SmallButtons
        onRestart={vi.fn()}
        onHome={vi.fn()}
        onCycleAnimation={vi.fn()}
        onSettings={vi.fn()}
        onHelp={vi.fn()}
        onVoice={vi.fn()}
      />
    );
    expect(screen.getAllByRole("button")).toHaveLength(6);
  });

  it("renders no disabled buttons when all handlers are provided", () => {
    render(
      <SmallButtons
        onRestart={vi.fn()}
        onHome={vi.fn()}
        onCycleAnimation={vi.fn()}
        onSettings={vi.fn()}
        onHelp={vi.fn()}
        onVoice={vi.fn()}
      />
    );
    const disabled = screen
      .getAllByRole("button")
      .filter((btn) => btn.hasAttribute("disabled"));
    expect(disabled).toHaveLength(0);
  });
});
