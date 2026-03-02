# AGENTS.md - Pixel Art Editor Agent Guide

This guide explains how coding agents (Codex, Claude Code, etc.) should interact
with the `pixel-art-editor` app using stable selectors and `window.pixelEditorApi`.

## Purpose

Use this document when you need to:

- create a new image from scratch,
- load the built-in `grot` base image and edit it,
- import an existing PNG and modify it,
- export the final result and verify it deterministically.

## Preconditions

- Run in development or test mode (API is not available in production builds).
- Start app in `pixel-art-editor/` with `npm run dev`.
- Wait until the page is loaded before interacting.

`window.pixelEditorApi` is exposed only in dev/test:

- available: `npm run dev`, Playwright test mode.
- not available: production build/preview intended for end users.

## Stable UI Selectors

Use these selectors for startup and UI-only actions.

### Startup screen

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

### Canvas, status, errors

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

## `window.pixelEditorApi` Contract

```ts
interface PixelEditorApi {
  setTool(tool: "brush" | "eraser" | "fill" | "picker"): void;
  setColor(color: [number, number, number, number] | string): void; // "#RGB" or "#RRGGBB"
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
  getBufferHash(): string; // FNV-1a checksum string
  getBuffer(): Uint8ClampedArray; // 64 * 64 * 4 bytes
  importPngFile(file: File): Promise<void>;
  exportPngBlob(): Promise<Blob>;
}
```

## Agent Interaction Rules

1. **Wait for API**
   - Check `window.pixelEditorApi` before using it.
2. **Operate in bounds**
   - Coordinates must be integers in `[0..63]`.
3. **Prefer deterministic API for pixel edits**
   - `setPixel` and `fill` are more reliable than pointer dragging for automation.
4. **Use UI selectors for startup transitions**
   - Especially for loading `grot`, which is a startup action.
5. **Verify with hash/state**
   - Use `getBufferHash()` and `getState()` to confirm expected outcomes.

## Common Workflows

### A) Create image from scratch

1. Open app.
2. Click `startup-start-new`.
3. Wait for editor mode and API availability.
4. Draw pixels/fills with API.
5. Export as blob and save.

Playwright-style example:

```ts
await page.goto("/");
await page.getByTestId("startup-start-new").click();
await page.waitForFunction(() => Boolean(window.pixelEditorApi));

await page.evaluate(() => {
  window.pixelEditorApi!.setPixel(0, 0, "#ffffff");
  window.pixelEditorApi!.setPixel(1, 0, "#f9c30c");
  window.pixelEditorApi!.fill(63, 63, "#000000");
});

const hash = await page.evaluate(() => window.pixelEditorApi!.getBufferHash());
```

### B) Load base `grot` image and edit it

`grot` is loaded from the startup screen.

1. Click `startup-load-grot`.
2. Wait for editor mode.
3. Apply edits via API (`setPixel`, `fill`) or tool buttons.
4. Verify with `getPixel`/`getBufferHash`.

```ts
await page.goto("/");
await page.getByTestId("startup-load-grot").click();
await page.waitForFunction(() => window.pixelEditorApi?.getState().phase === "editor");

await page.evaluate(() => {
  window.pixelEditorApi!.setPixel(10, 10, "#ee481b");
});
```

### C) Import existing PNG and edit it

Two reliable options:

- **Startup import:** use `startup-file-input` (enters editor after import)
- **In-editor import:** use `toolbar-import-input`

Startup example:

```ts
await page.goto("/");
await page.getByTestId("startup-file-input").setInputFiles("path/to/image.png");
await page.waitForFunction(() => window.pixelEditorApi?.getState().phase === "editor");
```

In-editor example:

```ts
await page.getByTestId("toolbar-import-input").setInputFiles("path/to/image.png");
```

Or via API directly:

```ts
await page.evaluate(async () => {
  const blob = await fetch("/my-image.png").then((r) => r.blob());
  const file = new File([blob], "my-image.png", { type: "image/png" });
  await window.pixelEditorApi!.importPngFile(file);
});
```

## Export and Save

### Option 1: UI export button

- Click `toolbar-export` to trigger browser download.

### Option 2: API export for deterministic tests

```ts
const bytes = await page.evaluate(async () => {
  const blob = await window.pixelEditorApi!.exportPngBlob();
  return Array.from(new Uint8Array(await blob.arrayBuffer()));
});
```

Use this path for roundtrip tests (export -> import -> hash compare).

## Validation Patterns

### Check a pixel

```ts
const px = await page.evaluate(() => window.pixelEditorApi!.getPixel(5, 7));
// [r, g, b, a]
```

### Check editor state

```ts
const state = await page.evaluate(() => window.pixelEditorApi!.getState());
// { phase, tool, color, showGrid, dirty, canUndo, canRedo }
```

### Check full-image integrity

```ts
const hash = await page.evaluate(() => window.pixelEditorApi!.getBufferHash());
```

## Error Handling and Recovery

- Out-of-range coordinates throw errors (`x/y` must be 0-63 integers).
- Invalid color strings throw `Invalid hex color`.
- Invalid imports surface UI errors (`startup-error` or `editor-error`).
- If API is undefined, ensure app is running in dev/test and page is fully loaded.

## Recommended Agent Sequence (Robust Default)

1. `goto("/")`
2. choose startup action (`startup-start-new`, `startup-load-grot`, or file input)
3. `waitForFunction(() => Boolean(window.pixelEditorApi))`
4. assert `getState().phase === "editor"`
5. perform edits via API
6. verify with `getPixel` or `getBufferHash`
7. export via API blob (tests) or UI export (user workflow)

