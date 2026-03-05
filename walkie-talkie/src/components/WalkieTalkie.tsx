import type { ReactNode } from "react";

interface WalkieTalkieProps {
  children: ReactNode;
}

const GRILLE_DOTS = 24;

/**
 * Outer shell/frame — the walkie-talkie housing.
 *
 * Renders the antenna, speaker grille (drag region), dark-red accent strip,
 * and the yellow inner panel that wraps all content children.
 */
export default function WalkieTalkie({ children }: WalkieTalkieProps) {
  return (
    <div className="app-root">
      <div className="device-body" data-testid="walkie-talkie-body">
        <div className="device-antenna" data-testid="device-antenna" />
        <div
          className="device-speaker-grille"
          data-testid="device-speaker-grille"
          data-tauri-drag-region
        >
          {Array.from({ length: GRILLE_DOTS }, (_, i) => (
            <span key={i} className="grille-dot" />
          ))}
        </div>
        <div className="device-accent-strip" />
        <div className="device-inner-panel">
          {children}
        </div>
      </div>
    </div>
  );
}
