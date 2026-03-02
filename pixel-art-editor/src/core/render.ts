import { PixelBuffer, W, H } from "./PixelBuffer";

export function renderToModel(pb: PixelBuffer, model: HTMLCanvasElement): void {
  model.width = W;
  model.height = H;
  const ctx = model.getContext("2d", { willReadFrequently: true })!;
  ctx.putImageData(new ImageData(new Uint8ClampedArray(pb.data), W, H), 0, 0);
}

export function renderToViewport(
  model: HTMLCanvasElement,
  viewport: HTMLCanvasElement,
  showGrid: boolean,
): void {
  const ctx = viewport.getContext("2d")!;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, viewport.width, viewport.height);
  ctx.drawImage(model, 0, 0, viewport.width, viewport.height);

  if (showGrid) drawGrid(ctx, viewport.width, viewport.height);
}

function drawGrid(ctx: CanvasRenderingContext2D, vw: number, vh: number): void {
  const cellW = vw / W;
  const cellH = vh / H;
  ctx.strokeStyle = "rgba(255,255,255,0.15)";
  ctx.lineWidth = 0.5;
  ctx.beginPath();
  for (let x = 0; x <= W; x++) {
    const px = Math.round(x * cellW) + 0.5;
    ctx.moveTo(px, 0);
    ctx.lineTo(px, vh);
  }
  for (let y = 0; y <= H; y++) {
    const py = Math.round(y * cellH) + 0.5;
    ctx.moveTo(0, py);
    ctx.lineTo(vw, py);
  }
  ctx.stroke();
}

export function pointerToCell(
  e: { clientX: number; clientY: number },
  canvas: HTMLCanvasElement,
): { x: number; y: number } | null {
  const rect = canvas.getBoundingClientRect();
  const nx = (e.clientX - rect.left) / rect.width;
  const ny = (e.clientY - rect.top) / rect.height;
  if (nx < 0 || nx >= 1 || ny < 0 || ny >= 1) return null;
  return { x: Math.floor(nx * W), y: Math.floor(ny * H) };
}
