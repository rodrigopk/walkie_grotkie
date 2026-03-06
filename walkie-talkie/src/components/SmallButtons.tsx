interface SmallButtonsProps {
  onQuit: () => void;
  onSettings?: () => void;
}

/**
 * Two rows of small function buttons below the PTT button.
 * The bottom-right quit button calls onQuit when clicked.
 * The second-from-right settings button calls onSettings when clicked.
 * All other buttons are currently disabled placeholders.
 */
export default function SmallButtons({ onQuit, onSettings }: SmallButtonsProps) {
  return (
    <div className="device-small-buttons" data-testid="small-buttons">
      <div className="device-small-buttons-row">
        <button className="small-btn" disabled aria-label="Function 1" />
        <button className="small-btn" disabled aria-label="Function 2" />
        <button className="small-btn" disabled aria-label="Function 3" />
        <button className="small-btn" disabled aria-label="Function 4" />
      </div>
      <div className="device-small-buttons-row">
        <button className="small-btn" disabled aria-label="Function 5" />
        <button className="small-btn" disabled aria-label="Function 6" />
        <button
          className="small-btn small-btn-settings"
          onClick={onSettings}
          aria-label="Settings"
          data-testid="settings-button"
        >
          ⚙
        </button>
        <button
          className="small-btn small-btn-quit"
          onClick={onQuit}
          aria-label="Quit application"
          data-testid="quit-button"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
