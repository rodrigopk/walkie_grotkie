import { useCallback, useState } from "react";

export type ButtonState = "idle" | "recording" | "processing" | "disabled";

interface PushToTalkButtonProps {
  onPressStart: () => void;
  onPressEnd: () => void;
  state: ButtonState;
}

const LABEL: Record<ButtonState, string> = {
  idle: "HOLD TO TALK",
  recording: "RECORDING...",
  processing: "WAIT...",
  disabled: "HOLD TO TALK",
};

const CSS_CLASS: Record<ButtonState, string> = {
  idle: "ptt-idle",
  recording: "ptt-recording",
  processing: "ptt-disabled",
  disabled: "ptt-disabled",
};

export default function PushToTalkButton({
  onPressStart,
  onPressEnd,
  state,
}: PushToTalkButtonProps) {
  const [isPointerDown, setIsPointerDown] = useState(false);
  const isInteractive = state === "idle" || state === "recording";

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (!isInteractive) return;
      // Capture the pointer so we receive pointerup even if the cursor moves off the button.
      (e.currentTarget as HTMLButtonElement).setPointerCapture(e.pointerId);
      setIsPointerDown(true);
      onPressStart();
    },
    [isInteractive, onPressStart]
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLButtonElement>) => {
      if (!isPointerDown) return;
      (e.currentTarget as HTMLButtonElement).releasePointerCapture(e.pointerId);
      setIsPointerDown(false);
      onPressEnd();
    },
    [isPointerDown, onPressEnd]
  );

  // Also fire onPressEnd if pointer leaves while captured (pointer cancel).
  const handlePointerCancel = useCallback(() => {
    if (!isPointerDown) return;
    setIsPointerDown(false);
    onPressEnd();
  }, [isPointerDown, onPressEnd]);

  const effectiveClass = isPointerDown && state === "recording"
    ? "ptt-pressed"
    : CSS_CLASS[state];

  return (
    <button
      className={`ptt-button ${effectiveClass}`}
      disabled={!isInteractive}
      aria-label={LABEL[state]}
      aria-pressed={state === "recording"}
      data-testid="ptt-button"
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
    >
      <span className="ptt-label" data-testid="ptt-label">
        {LABEL[state]}
      </span>
    </button>
  );
}
