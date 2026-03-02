import { PixelBuffer, W, H } from "./PixelBuffer";

export async function exportPng(
  model: HTMLCanvasElement,
  filename = "pixel-art-64x64.png",
): Promise<void> {
  const blob = await new Promise<Blob>((resolve, reject) => {
    model.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("toBlob failed"))),
      "image/png",
    );
  });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function importPng(
  file: File,
  model: HTMLCanvasElement,
): Promise<PixelBuffer> {
  if (file.type && file.type !== "image/png") {
    throw new Error(`Expected image/png, got ${file.type}`);
  }
  const bitmap = await createImageBitmap(file);
  if (bitmap.width !== W || bitmap.height !== H) {
    throw new Error(
      `Expected ${W}×${H}, got ${bitmap.width}×${bitmap.height}`,
    );
  }
  model.width = W;
  model.height = H;
  const ctx = model.getContext("2d", { willReadFrequently: true })!;
  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(bitmap, 0, 0);
  const imgData = ctx.getImageData(0, 0, W, H);
  return new PixelBuffer(imgData.data);
}

export async function loadDefaultAsset(
  url: string,
  model: HTMLCanvasElement,
): Promise<PixelBuffer> {
  const resp = await fetch(url);
  const blob = await resp.blob();
  const file = new File([blob], "default.png", { type: "image/png" });
  return importPng(file, model);
}
