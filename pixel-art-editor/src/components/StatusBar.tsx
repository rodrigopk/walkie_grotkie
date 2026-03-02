import type { RGBA } from "../core/PixelBuffer";
import type { ToolType } from "../core/tools";
import "./StatusBar.css";

interface StatusBarProps {
  cursorInfo: { x: number; y: number; color: RGBA } | null;
  tool: ToolType;
  dirty: boolean;
}

function rgbaToHex(rgba: RGBA): string {
  return (
    "#" +
    rgba
      .slice(0, 3)
      .map((c) => c.toString(16).padStart(2, "0"))
      .join("")
  );
}

const TOOL_LABELS: Record<ToolType, string> = {
  brush: "Brush",
  eraser: "Eraser",
  fill: "Fill",
  picker: "Picker",
};

export function StatusBar({ cursorInfo, tool, dirty }: StatusBarProps) {
  return (
    <div className="status-bar">
      <span className="status-item">
        {cursorInfo
          ? `(${cursorInfo.x}, ${cursorInfo.y})`
          : "—"}
      </span>
      <span className="status-item">
        {cursorInfo && (
          <>
            <span
              className="status-color-swatch"
              style={{ background: rgbaToHex(cursorInfo.color) }}
            />
            {rgbaToHex(cursorInfo.color)}
          </>
        )}
      </span>
      <span className="status-item">{TOOL_LABELS[tool]}</span>
      {dirty && <span className="status-item status-dirty">Modified</span>}
    </div>
  );
}
