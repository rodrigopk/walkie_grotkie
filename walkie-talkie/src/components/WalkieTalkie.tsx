import type { ReactNode } from "react";
import { FaPowerOff } from "react-icons/fa6";

interface WalkieTalkieProps {
  children: ReactNode;
  onQuit?: () => void;
}

const GRILLE_DOTS_ROW1 = 22;
const GRILLE_DOTS_ROW2 = 22;

/**
 * Outer shell/frame — the walkie-talkie housing.
 *
 * Renders the antenna (above device-body), speaker grille (drag region, two
 * rows of dots), dark-red accent strip, and the yellow inner panel that wraps
 * all content children.
 *
 * The OFF button lives in the top-left of the first grille row and closes the
 * app. Both grille rows act as the window drag region.
 */
export default function WalkieTalkie({ children, onQuit }: WalkieTalkieProps) {
  return (
    <div className="app-root">
      <div className="device-wrapper">
        <div className="device-antenna-container">
          <div className="device-antenna" data-testid="device-antenna" />
        </div>
        <div className="device-body" data-testid="walkie-talkie-body">
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
              <FaPowerOff />
            </button>
            <div className="grille-dots-container">
              <div className="grille-dots" data-tauri-drag-region>
                {Array.from({ length: GRILLE_DOTS_ROW1 }, (_, i) => (
                  <span key={i} className="grille-dot" />
                ))}
              </div>
              <div className="grille-dots" data-tauri-drag-region>
                {Array.from({ length: GRILLE_DOTS_ROW2 }, (_, i) => (
                  <span key={i} className="grille-dot" />
                ))}
              </div>
            </div>
          </div>
          <div className="device-accent-strip" />
          <div className="device-inner-panel">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
