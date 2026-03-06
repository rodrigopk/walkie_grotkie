import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import VoiceView, { VOICES } from "../components/VoiceView";
import type { VoiceName } from "../components/VoiceView";

const noop = vi.fn().mockResolvedValue(undefined);

function makePreview(impl?: () => Promise<void>) {
  return vi.fn(impl ?? (() => Promise.resolve()));
}

describe("VoiceView", () => {
  // ── Rendering ─────────────────────────────────────────────────
  it("renders the voice-view container", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getByTestId("voice-view")).toBeInTheDocument();
  });

  it("renders the screen title header", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getByTestId("screen-title")).toBeInTheDocument();
  });

  it("screen title reads 'Voice'", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getByTestId("screen-title")).toHaveTextContent("Voice");
  });

  it("renders all 10 voice options", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getAllByRole("button")).toHaveLength(VOICES.length);
  });

  it("renders a button for every voice name", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    for (const v of VOICES) {
      expect(screen.getByTestId(`voice-option-${v}`)).toBeInTheDocument();
    }
  });

  it("displays voice names capitalised", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getByText("Nova")).toBeInTheDocument();
    expect(screen.getByText("Alloy")).toBeInTheDocument();
  });

  // ── Selection state ───────────────────────────────────────────
  it("marks the currentVoice button as pressed", () => {
    render(
      <VoiceView currentVoice="coral" onSelect={noop} previewVoice={makePreview()} />
    );
    expect(screen.getByTestId("voice-option-coral")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("marks all other voice buttons as not pressed", () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );
    for (const v of VOICES) {
      const expected = v === "nova" ? "true" : "false";
      expect(screen.getByTestId(`voice-option-${v}`)).toHaveAttribute(
        "aria-pressed",
        expected
      );
    }
  });

  // ── Interaction ───────────────────────────────────────────────
  it("calls onSelect with the chosen voice when clicked", async () => {
    const onSelect = vi.fn();
    render(
      <VoiceView
        currentVoice="nova"
        onSelect={onSelect}
        previewVoice={makePreview()}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-coral"));
    });

    expect(onSelect).toHaveBeenCalledWith("coral");
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("calls previewVoice with the chosen voice when clicked", async () => {
    const previewVoice = makePreview();
    render(
      <VoiceView
        currentVoice="nova"
        onSelect={noop}
        previewVoice={previewVoice}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-alloy"));
    });

    expect(previewVoice).toHaveBeenCalledWith("alloy");
  });

  it("updates the selected voice in UI after clicking", async () => {
    render(
      <VoiceView
        currentVoice="nova"
        onSelect={noop}
        previewVoice={makePreview()}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-ash"));
    });

    expect(screen.getByTestId("voice-option-ash")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByTestId("voice-option-nova")).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  // ── Preview state ─────────────────────────────────────────────
  it("adds voice-previewing class to the row while preview is playing", async () => {
    let resolvePreview!: () => void;
    const slowPreview = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolvePreview = resolve;
        })
    );

    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={slowPreview} />
    );

    // Start the click but don't await — we want to inspect mid-preview state.
    act(() => {
      fireEvent.click(screen.getByTestId("voice-option-echo"));
    });

    expect(screen.getByTestId("voice-option-echo")).toHaveClass(
      "voice-previewing"
    );

    // Finish preview.
    await act(async () => {
      resolvePreview();
    });
  });

  it("removes voice-previewing class after preview completes", async () => {
    render(
      <VoiceView
        currentVoice="nova"
        onSelect={noop}
        previewVoice={makePreview()}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-sage"));
    });

    expect(screen.getByTestId("voice-option-sage")).not.toHaveClass(
      "voice-previewing"
    );
  });

  it("removes voice-previewing class even if preview throws", async () => {
    const failingPreview = vi.fn<(v: VoiceName) => Promise<void>>(() =>
      Promise.reject(new Error("TTS failed"))
    );

    render(
      <VoiceView
        currentVoice="nova"
        onSelect={noop}
        previewVoice={failingPreview}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-onyx"));
    });

    expect(screen.getByTestId("voice-option-onyx")).not.toHaveClass(
      "voice-previewing"
    );
  });

  it("keeps the selection even if the preview throws", async () => {
    const failingPreview = vi.fn<(v: VoiceName) => Promise<void>>(() =>
      Promise.reject(new Error("TTS failed"))
    );
    const onSelect = vi.fn();

    render(
      <VoiceView
        currentVoice="nova"
        onSelect={onSelect}
        previewVoice={failingPreview}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-verse"));
    });

    expect(onSelect).toHaveBeenCalledWith("verse");
    expect(screen.getByTestId("voice-option-verse")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  // ── Spinner ───────────────────────────────────────────────────
  it("shows a spinner while the preview is loading", async () => {
    let resolvePreview!: () => void;
    const slowPreview = vi.fn(
      () => new Promise<void>((resolve) => { resolvePreview = resolve; })
    );

    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={slowPreview} />
    );

    act(() => {
      fireEvent.click(screen.getByTestId("voice-option-echo"));
    });

    expect(screen.getByTestId("voice-preview-spinner")).toBeInTheDocument();

    await act(async () => { resolvePreview(); });
  });

  it("removes the spinner after preview completes", async () => {
    render(
      <VoiceView currentVoice="nova" onSelect={noop} previewVoice={makePreview()} />
    );

    await act(async () => {
      fireEvent.click(screen.getByTestId("voice-option-sage"));
    });

    expect(screen.queryByTestId("voice-preview-spinner")).not.toBeInTheDocument();
  });

  // ── Concurrency guard ─────────────────────────────────────────
  it("ignores clicks on other voices while a preview is in-flight", async () => {
    let resolvePreview!: () => void;
    const slowPreview = vi.fn(
      () => new Promise<void>((resolve) => { resolvePreview = resolve; })
    );
    const onSelect = vi.fn();

    render(
      <VoiceView currentVoice="nova" onSelect={onSelect} previewVoice={slowPreview} />
    );

    act(() => {
      fireEvent.click(screen.getByTestId("voice-option-echo"));
    });
    expect(onSelect).toHaveBeenCalledTimes(1);

    act(() => {
      fireEvent.click(screen.getByTestId("voice-option-coral"));
    });

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(slowPreview).toHaveBeenCalledTimes(1);

    await act(async () => { resolvePreview(); });
  });
});
