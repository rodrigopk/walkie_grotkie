import { PixelBuffer, W, H } from "./PixelBuffer";
import type { RGBA } from "./PixelBuffer";

export type ToolType = "brush" | "eraser" | "fill" | "picker";

export function applyBrush(pb: PixelBuffer, x: number, y: number, color: RGBA): void {
  pb.setRGBA(x, y, ...color);
}

export function applyEraser(pb: PixelBuffer, x: number, y: number): void {
  pb.setRGBA(x, y, 0, 0, 0, 255);
}

export function applyFill(pb: PixelBuffer, sx: number, sy: number, fill: RGBA): void {
  const target = pb.getRGBA(sx, sy);
  if (rgbaEqual(target, fill)) return;

  const stack: [number, number][] = [[sx, sy]];
  while (stack.length) {
    const [x, y] = stack.pop()!;
    if (x < 0 || x >= W || y < 0 || y >= H) continue;
    if (!rgbaEqual(pb.getRGBA(x, y), target)) continue;
    pb.setRGBA(x, y, ...fill);
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
}

export function pickColor(pb: PixelBuffer, x: number, y: number): RGBA {
  return pb.getRGBA(x, y);
}

function rgbaEqual(a: RGBA, b: RGBA): boolean {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}
