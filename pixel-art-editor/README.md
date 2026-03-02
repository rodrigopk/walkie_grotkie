# Pixel Art Editor

64x64 pixel editor with import/export support and an automation contract for coding agents.

## Scripts

- `npm run dev` - start local Vite dev server.
- `npm run build` - run TypeScript build + production bundle.
- `npm run lint` - run ESLint.
- `npm run test` - run Vitest unit tests.
- `npm run e2e` - run Playwright E2E tests.
- `npm run e2e:headed` - run Playwright with visible browser.

## Agent Automation Contract

The app exposes two automation surfaces:

1. Stable selectors (`data-testid`) and accessible labels for UI controls.
2. A development/test API on `window.pixelEditorApi` for deterministic canvas operations.

### Important limits

- `window.pixelEditorApi` is available only in development and test modes.
- Production builds do not expose this API.
- Use UI selectors when you want user-like interactions; use the API for deterministic pixel operations/assertions.

## Stable Selectors

### Startup

- `startup-start-new`
- `startup-load-grot`
- `startup-open-file`
- `startup-file-input`
- `startup-error`

### Toolbar

- `tool-brush`
- `tool-eraser`
- `tool-fill`
- `tool-picker`
- `toolbar-undo`
- `toolbar-redo`
- `toolbar-grid-toggle`
- `toolbar-export`
- `toolbar-import`
- `toolbar-import-input`
- `toolbar-new`

### Canvas and Status

- `canvas-viewport-wrapper`
- `canvas-viewport`
- `model-canvas`
- `status-bar`
- `status-cursor`
- `status-color`
- `status-tool`
- `status-dirty`
- `editor-error`
- `editor-error-dismiss`

### Colors

- `color-current`
- `color-current-swatch`
- `color-current-hex`
- `color-picker-input`
- `color-swatch-<index>`

## `window.pixelEditorApi` Methods

```ts
interface PixelEditorApi {
  setTool(tool: "brush" | "eraser" | "fill" | "picker"): void;
  setColor(color: [number, number, number, number] | string): void; // string: #RGB or #RRGGBB
  setPixel(x: number, y: number, color?: [number, number, number, number] | string): void;
  fill(x: number, y: number, color?: [number, number, number, number] | string): void;
  getPixel(x: number, y: number): [number, number, number, number];
  getState(): {
    phase: "startup" | "editor";
    tool: "brush" | "eraser" | "fill" | "picker";
    color: [number, number, number, number];
    showGrid: boolean;
    dirty: boolean;
    canUndo: boolean;
    canRedo: boolean;
  };
  getBufferHash(): string;
  getBuffer(): Uint8ClampedArray;
  importPngFile(file: File): Promise<void>;
  exportPngBlob(): Promise<Blob>;
}
```

## Example Agent Session

```ts
await page.goto("/");
await page.getByTestId("startup-start-new").click();
await page.waitForFunction(() => Boolean(window.pixelEditorApi));

await page.evaluate(() => {
  window.pixelEditorApi?.setColor("#ff0000");
  window.pixelEditorApi?.setPixel(10, 10);
});

const hash = await page.evaluate(() => window.pixelEditorApi?.getBufferHash());
expect(hash).toBeTruthy();
```
