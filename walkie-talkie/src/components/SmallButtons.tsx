interface SmallButtonsProps {
  onRestart?: () => void;
  onHome?: () => void;
  onCycleAnimation?: () => void;
  onSettings?: () => void;
}

/**
 * Two rows of small function buttons below the PTT button.
 *
 * Bottom row (left to right):
 *   ⌂ Home        — navigates back to the main screen
 *   ✦ Anim cycle  — cycles through Grot animations
 *   ⚙ Settings    — opens the settings view
 *   ↻ Restart     — tears down and restarts the BLE + OpenAI session
 *
 * Top row buttons are disabled placeholders.
 */
export default function SmallButtons({
  onRestart,
  onHome,
  onCycleAnimation,
  onSettings,
}: SmallButtonsProps) {
  return (
    <div className="device-small-buttons" data-testid="small-buttons">
      <div className="device-small-buttons-row">
        <button className="small-btn" disabled aria-label="Function 1" />
        <button className="small-btn" disabled aria-label="Function 2" />
        <button className="small-btn" disabled aria-label="Function 3" />
        <button className="small-btn" disabled aria-label="Function 4" />
      </div>
      <div className="device-small-buttons-row">
        <button
          className="small-btn small-btn-home"
          onClick={onHome}
          aria-label="Home"
          data-testid="home-button"
        >
          ⌂
        </button>
        <button
          className="small-btn small-btn-anim"
          onClick={onCycleAnimation}
          aria-label="Cycle animation"
          data-testid="cycle-animation-button"
        >
          ✦
        </button>
        <button
          className="small-btn small-btn-settings"
          onClick={onSettings}
          aria-label="Settings"
          data-testid="settings-button"
        >
          ⚙
        </button>
        <button
          className="small-btn small-btn-restart"
          onClick={onRestart}
          aria-label="Restart session"
          data-testid="restart-button"
        >
          ↻
        </button>
      </div>
    </div>
  );
}
