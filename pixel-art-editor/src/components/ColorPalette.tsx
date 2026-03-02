import type { RGBA } from "../core/PixelBuffer";
import "./ColorPalette.css";

interface ColorPaletteProps {
  color: RGBA;
  onSetColor: (color: RGBA) => void;
}

const PALETTE = {
  black: [0, 0, 0, 255],
  white: [255, 255, 255, 255],
  grayMid: [127, 127, 127, 255],
  grayLight: [195, 195, 195, 255],

  redBright: [255, 0, 0, 255],
  orangeBright: [238, 72, 27, 255],
  yellowBright: [249, 195, 12, 255],
  greenBright: [0, 255, 0, 255],

  cyanBright: [0, 255, 255, 255],
  blueBright: [0, 0, 255, 255],
  purpleBright: [127, 0, 255, 255],
  magentaBright: [255, 0, 255, 255],

  redDark: [127, 0, 0, 255],
  orangeDark: [127, 63, 0, 255],
  yellowDark: [127, 127, 0, 255],
  greenDark: [0, 127, 0, 255],

  cyanDark: [0, 127, 127, 255],
  blueDark: [0, 0, 127, 255],
  purpleDark: [63, 0, 127, 255],
  magentaDark: [127, 0, 127, 255],

  redPastel: [255, 200, 200, 255],
  orangePastel: [255, 220, 180, 255],
  yellowPastel: [255, 255, 200, 255],
  greenPastel: [200, 255, 200, 255],
} as const satisfies Record<string, RGBA>;

const SWATCH_ORDER = [
  "black",
  "white",
  "grayMid",
  "grayLight",
  "redBright",
  "orangeBright",
  "yellowBright",
  "greenBright",
  "cyanBright",
  "blueBright",
  "purpleBright",
  "magentaBright",
  "redDark",
  "orangeDark",
  "yellowDark",
  "greenDark",
  "cyanDark",
  "blueDark",
  "purpleDark",
  "magentaDark",
  "redPastel",
  "orangePastel",
  "yellowPastel",
  "greenPastel",
] as const;

const SWATCHES = SWATCH_ORDER.map((name) => ({
  name,
  rgba: PALETTE[name],
}));

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
            key={swatch.name}
            className={`color-swatch ${rgbaEqual(swatch.rgba, color) ? "active" : ""}`}
            style={{ background: rgbaToHex(swatch.rgba) }}
            onClick={() => onSetColor(swatch.rgba)}
            title={rgbaToHex(swatch.rgba)}
            aria-label={`Select color ${swatch.name}`}
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
