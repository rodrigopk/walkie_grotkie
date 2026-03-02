import type { RGBA } from "../core/PixelBuffer";
import "./ColorPalette.css";

interface ColorPaletteProps {
  color: RGBA;
  onSetColor: (color: RGBA) => void;
}

const SWATCHES: RGBA[] = [
  [0, 0, 0, 255],
  [255, 255, 255, 255],
  [127, 127, 127, 255],
  [195, 195, 195, 255],

  [255, 0, 0, 255],
  [255, 127, 0, 255],
  [255, 255, 0, 255],
  [0, 255, 0, 255],

  [0, 255, 255, 255],
  [0, 0, 255, 255],
  [127, 0, 255, 255],
  [255, 0, 255, 255],

  [127, 0, 0, 255],
  [127, 63, 0, 255],
  [127, 127, 0, 255],
  [0, 127, 0, 255],

  [0, 127, 127, 255],
  [0, 0, 127, 255],
  [63, 0, 127, 255],
  [127, 0, 127, 255],

  [255, 200, 200, 255],
  [255, 220, 180, 255],
  [255, 255, 200, 255],
  [200, 255, 200, 255],
];

function rgbaToHex(rgba: RGBA): string {
  return (
    "#" +
    rgba
      .slice(0, 3)
      .map((c) => c.toString(16).padStart(2, "0"))
      .join("")
  );
}

function hexToRgba(hex: string): RGBA {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b, 255];
}

function rgbaEqual(a: RGBA, b: RGBA): boolean {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}

export function ColorPalette({ color, onSetColor }: ColorPaletteProps) {
  return (
    <div className="color-palette">
      <div className="color-current" data-testid="color-current">
        <div
          className="color-current-swatch"
          style={{ background: rgbaToHex(color) }}
          aria-label={`Current color ${rgbaToHex(color)}`}
          data-testid="color-current-swatch"
        />
        <span className="color-current-hex" data-testid="color-current-hex">
          {rgbaToHex(color)}
        </span>
      </div>

      <div className="color-swatches">
        {SWATCHES.map((swatch, i) => (
          <button
            key={i}
            className={`color-swatch ${rgbaEqual(swatch, color) ? "active" : ""}`}
            style={{ background: rgbaToHex(swatch) }}
            onClick={() => onSetColor(swatch)}
            title={rgbaToHex(swatch)}
            aria-label={`Select color ${rgbaToHex(swatch)}`}
            data-testid={`color-swatch-${i}`}
          />
        ))}
      </div>

      <label className="color-picker-label">
        Custom
        <input
          type="color"
          className="color-picker-input"
          value={rgbaToHex(color)}
          onChange={(e) => onSetColor(hexToRgba(e.target.value))}
          aria-label="Custom color picker"
          data-testid="color-picker-input"
        />
      </label>
    </div>
  );
}
