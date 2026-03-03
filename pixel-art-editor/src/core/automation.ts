import type { RGBA } from "./PixelBuffer";
import type { ToolType } from "./tools";

export interface PixelEditorBridgeState {
  phase: "startup" | "editor";
  tool: ToolType;
  color: RGBA;
  showGrid: boolean;
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
}

export interface PixelEditorApi {
  setTool: (tool: ToolType) => void;
  setColor: (color: RGBA | string) => void;
  setPixel: (x: number, y: number, color?: RGBA | string) => void;
  fill: (x: number, y: number, color?: RGBA | string) => void;
  getPixel: (x: number, y: number) => RGBA;
  getState: () => PixelEditorBridgeState;
  getBufferHash: () => string;
  getBuffer: () => Uint8ClampedArray;
  importPngFile: (file: File) => Promise<void>;
  exportPngBlob: () => Promise<Blob>;
  exportPngBlobToPath: (filePath: string) => Promise<void>;
}

declare global {
  interface Window {
    pixelEditorApi?: PixelEditorApi;
  }
}

function normalizeHex(hex: string): string {
  if (/^#[0-9a-fA-F]{6}$/.test(hex)) return hex.toLowerCase();
  if (/^#[0-9a-fA-F]{3}$/.test(hex)) {
    const r = hex[1];
    const g = hex[2];
    const b = hex[3];
    return `#${r}${r}${g}${g}${b}${b}`.toLowerCase();
  }
  throw new Error(`Invalid hex color: ${hex}`);
}

export function parseColorInput(color: RGBA | string): RGBA {
  if (typeof color !== "string") return color;
  const normalized = normalizeHex(color);
  return [
    Number.parseInt(normalized.slice(1, 3), 16),
    Number.parseInt(normalized.slice(3, 5), 16),
    Number.parseInt(normalized.slice(5, 7), 16),
    255,
  ];
}

export function hashBytes(bytes: Uint8ClampedArray): string {
  // FNV-1a 32-bit hash; stable and fast for 16KB pixel buffers.
  let hash = 0x811c9dc5;
  for (let i = 0; i < bytes.length; i++) {
    hash ^= bytes[i];
    hash = Math.imul(hash, 0x01000193);
  }
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

export function shouldExposeAutomationApi(): boolean {
  return import.meta.env.DEV || import.meta.env.MODE === "test";
}

export function attachPixelEditorApi(api: PixelEditorApi): () => void {
  window.pixelEditorApi = api;
  return () => {
    if (window.pixelEditorApi === api) {
      delete window.pixelEditorApi;
    }
  };
}

