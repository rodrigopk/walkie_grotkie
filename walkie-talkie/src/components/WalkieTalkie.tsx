import type { ReactNode } from "react";

interface WalkieTalkieProps {
  children: ReactNode;
  onQuit?: () => void;
}

const GRILLE_DOTS = 24;

/**
 * Outer shell/frame — the walkie-talkie housing.
 *
 * Renders the antenna, speaker grille (drag region), dark-red accent strip,
 * and the yellow inner panel that wraps all content children.
 *
 * The OFF button lives in the top-left of the grille and closes the app.
 * The rest of the grille acts as the window drag region.
 */
export default function WalkieTalkie({ children, onQuit }: WalkieTalkieProps) {
  return (
    <div className="app-root">
      <div className="device-body" data-testid="walkie-talkie-body">
        <div className="device-antenna" data-testid="device-antenna" />
        <div
          className="device-speaker-grille"
          data-testid="device-speaker-grille"
          data-tauri-drag-region
        >
          <button
            className="off-btn"
            onClick={onQuit}
            aria-label="Turn off"
            data-testid="off-button"
          >
            OFF
          </button>
          <div className="grille-dots" data-tauri-drag-region>
            {Array.from({ length: GRILLE_DOTS }, (_, i) => (
              <span key={i} className="grille-dot" />
            ))}
          </div>
        </div>
        <div className="device-accent-strip" />
        <div className="device-inner-panel">
          {children}
        </div>
      </div>
    </div>
  );
}
