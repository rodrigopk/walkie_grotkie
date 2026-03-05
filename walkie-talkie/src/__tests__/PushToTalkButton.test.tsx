import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PushToTalkButton, {
  type ButtonState,
} from "../components/PushToTalkButton";

function renderBtn(
  state: ButtonState = "idle",
  onPressStart = vi.fn(),
  onPressEnd = vi.fn()
) {
  return render(
    <PushToTalkButton
      state={state}
      onPressStart={onPressStart}
      onPressEnd={onPressEnd}
    />
  );
}

describe("PushToTalkButton", () => {
  it("renders with idle label by default", () => {
    renderBtn("idle");
    expect(screen.getByTestId("ptt-label")).toHaveTextContent("HOLD TO TALK");
  });

  it("shows RECORDING... label when recording", () => {
    renderBtn("recording");
    expect(screen.getByTestId("ptt-label")).toHaveTextContent("RECORDING...");
  });

  it("shows WAIT... label when processing", () => {
    renderBtn("processing");
    expect(screen.getByTestId("ptt-label")).toHaveTextContent("WAIT...");
  });

  it("shows HOLD TO TALK label when disabled", () => {
    renderBtn("disabled");
    expect(screen.getByTestId("ptt-label")).toHaveTextContent("HOLD TO TALK");
  });

  it("calls onPressStart on pointerdown when idle", () => {
    const onPressStart = vi.fn();
    renderBtn("idle", onPressStart);
    fireEvent.pointerDown(screen.getByTestId("ptt-button"));
    expect(onPressStart).toHaveBeenCalledOnce();
  });

  it("calls onPressEnd on pointerup after press", () => {
    const onPressStart = vi.fn();
    const onPressEnd = vi.fn();
    renderBtn("recording", onPressStart, onPressEnd);
    const btn = screen.getByTestId("ptt-button");
    fireEvent.pointerDown(btn);
    fireEvent.pointerUp(btn);
    expect(onPressEnd).toHaveBeenCalledOnce();
  });

  it("is disabled when state is processing", () => {
    renderBtn("processing");
    expect(screen.getByTestId("ptt-button")).toBeDisabled();
  });

  it("is disabled when state is disabled", () => {
    renderBtn("disabled");
    expect(screen.getByTestId("ptt-button")).toBeDisabled();
  });

  it("is enabled (not disabled) when idle", () => {
    renderBtn("idle");
    expect(screen.getByTestId("ptt-button")).not.toBeDisabled();
  });

  it("is enabled (not disabled) when recording", () => {
    renderBtn("recording");
    expect(screen.getByTestId("ptt-button")).not.toBeDisabled();
  });

  it("does not call onPressStart when disabled", () => {
    const onPressStart = vi.fn();
    renderBtn("disabled", onPressStart);
    fireEvent.pointerDown(screen.getByTestId("ptt-button"));
    expect(onPressStart).not.toHaveBeenCalled();
  });

  it("does not call onPressStart when processing", () => {
    const onPressStart = vi.fn();
    renderBtn("processing", onPressStart);
    fireEvent.pointerDown(screen.getByTestId("ptt-button"));
    expect(onPressStart).not.toHaveBeenCalled();
  });

  it("has ptt-idle class when idle", () => {
    renderBtn("idle");
    expect(screen.getByTestId("ptt-button")).toHaveClass("ptt-idle");
  });

  it("has ptt-disabled class when processing", () => {
    renderBtn("processing");
    expect(screen.getByTestId("ptt-button")).toHaveClass("ptt-disabled");
  });

  it("has aria-pressed false when idle", () => {
    renderBtn("idle");
    expect(screen.getByTestId("ptt-button")).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("has aria-pressed true when recording", () => {
    renderBtn("recording");
    expect(screen.getByTestId("ptt-button")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
});
