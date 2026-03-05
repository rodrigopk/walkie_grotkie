import type { ReactNode } from "react";

interface WalkieTalkieProps {
  children: ReactNode;
}

const GRILLE_DOTS = 30;

/**
 * Outer shell/frame — the walkie-talkie housing.
 *
 * Renders the antenna, speaker grille, and the main body that wraps
 * whatever content (LED display + PTT button) is passed as children.
 */
export default function WalkieTalkie({ children }: WalkieTalkieProps) {
  return (
    <div className="app-root">
      <div className="device-body" data-testid="walkie-talkie-body">
        <div className="device-antenna" data-testid="device-antenna" />
        <div className="device-speaker-grille" data-testid="device-speaker-grille">
          {Array.from({ length: GRILLE_DOTS }, (_, i) => (
            <span key={i} className="grille-dot" />
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}
