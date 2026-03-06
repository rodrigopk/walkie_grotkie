import { useState, useCallback } from "react";

export const VOICES = [
  "alloy",
  "ash",
  "coral",
  "echo",
  "fable",
  "nova",
  "onyx",
  "sage",
  "shimmer",
  "verse",
] as const;

export type VoiceName = (typeof VOICES)[number];

interface VoiceViewProps {
  currentVoice: VoiceName;
  /** Called immediately when the user picks a voice (before preview finishes). */
  onSelect: (voice: VoiceName) => void;
  /** Should play a short audio preview for the given voice; may throw. */
  previewVoice: (voice: VoiceName) => Promise<void>;
}

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

/**
 * Voice picker screen displayed inside the visor.
 *
 * Clicking a row immediately selects that voice (calls onSelect) and
 * fires a live TTS preview. While a preview is in-flight all other picks
 * are blocked. The row dims while the preview is loading/playing.
 * Selections persist even if the preview fails.
 */
export default function VoiceView({
  currentVoice,
  onSelect,
  previewVoice,
}: VoiceViewProps) {
  const [selected, setSelected] = useState<VoiceName>(currentVoice);
  const [previewing, setPreviewing] = useState<VoiceName | null>(null);

  const handlePick = useCallback(
    async (voice: VoiceName) => {
      if (previewing) return;
      setSelected(voice);
      onSelect(voice);
      setPreviewing(voice);
      try {
        await previewVoice(voice);
      } catch {
        // Preview failed — the voice selection is already committed; just skip audio.
      } finally {
        setPreviewing(null);
      }
    },
    [onSelect, previewVoice, previewing],
  );

  return (
    <div className="device-screen" data-testid="voice-view">
      <div className="screen-header" data-testid="screen-title">Voice</div>
      <div className="voice-view">
        <div className="voice-list">
          {VOICES.map((v) => (
            <button
              key={v}
              className={cx("voice-option", previewing === v && "voice-previewing")}
              onClick={() => void handlePick(v)}
              data-testid={`voice-option-${v}`}
              aria-pressed={selected === v}
            >
              {previewing === v ? (
                <span className="voice-preview-spinner" data-testid="voice-preview-spinner" />
              ) : (
                <span className={cx("voice-radio", selected === v && "voice-radio-selected")}>
                  {selected === v && <span className="voice-radio-dot" />}
                </span>
              )}
              <span className="voice-name">
                {v.charAt(0).toUpperCase() + v.slice(1)}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
