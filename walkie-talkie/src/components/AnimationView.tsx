import { useState, useCallback } from "react";

export const ANIMATIONS = [
  "idle",
  "thinking",
  "talking",
  "excited",
  "dancing",
  "sleeping",
  "surprised",
] as const;

export type AnimationName = (typeof ANIMATIONS)[number];

interface AnimationViewProps {
  currentAnimation: AnimationName;
  onSelect: (animation: AnimationName) => void;
}

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

/**
 * Animation picker screen displayed inside the visor.
 *
 * Clicking a row selects that animation and immediately sends it to
 * the LED device. The animation keeps playing until another is sent.
 */
export default function AnimationView({
  currentAnimation,
  onSelect,
}: AnimationViewProps) {
  const [selected, setSelected] = useState<AnimationName>(currentAnimation);
  const [sending, setSending] = useState<AnimationName | null>(null);

  const handlePick = useCallback(
    (animation: AnimationName) => {
      if (sending) return;
      setSelected(animation);
      setSending(animation);
      onSelect(animation);
      // Brief visual feedback before clearing the spinner.
      setTimeout(() => setSending(null), 600);
    },
    [onSelect, sending],
  );

  return (
    <div className="device-screen" data-testid="animation-view">
      <div className="screen-header" data-testid="screen-title">Animations</div>
      <div className="voice-view">
        <div className="voice-list">
          {ANIMATIONS.map((a) => (
            <button
              key={a}
              className={cx("voice-option", sending === a && "voice-previewing")}
              onClick={() => void handlePick(a)}
              data-testid={`animation-option-${a}`}
              aria-pressed={selected === a}
            >
              {sending === a ? (
                <span className="voice-preview-spinner" data-testid="animation-sending-spinner" />
              ) : (
                <span className={cx("voice-radio", selected === a && "voice-radio-selected")}>
                  {selected === a && <span className="voice-radio-dot" />}
                </span>
              )}
              <span className="voice-name">
                {a.charAt(0).toUpperCase() + a.slice(1)}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
