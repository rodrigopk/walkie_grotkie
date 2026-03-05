interface SmallButtonsProps {
  onQuit: () => void;
}

/**
 * Two rows of small function buttons below the PTT button.
 * All buttons are currently disabled placeholders except the bottom-right
 * quit button, which calls onQuit when clicked.
 */
export default function SmallButtons({ onQuit }: SmallButtonsProps) {
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
        <button className="small-btn" disabled aria-label="Function 7" />
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
