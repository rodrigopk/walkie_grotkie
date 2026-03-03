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
  exportPngBlobToPath(filePath: string): Promise<void>;
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

## Grot Character Reference

### Loading the default grot image

The only way to load grot is from the **startup screen** before entering the
editor. Click the button with `data-testid="startup-load-grot"` (labelled
"Load grot default image"). This is a one-time transition — once in editor
mode there is no "load grot" action; use undo or restart if you need to reset.

```ts
await page.goto("/");
await page.getByTestId("startup-load-grot").click();
await page.waitForFunction(() => window.pixelEditorApi?.getState().phase === "editor");
```

When operating from a browser automation tool that only supports navigation
(no `page.evaluate`), the startup transition can be triggered by clicking the
button ref obtained from a snapshot, then entering the editor by waiting for
the toolbar buttons to appear.

### Identifying the grot character outline

The grot image uses **alpha transparency** to separate character pixels from
the background:

- **Background pixels:** `alpha === 0` (fully transparent `[r, g, b, 0]`)
- **Character pixels:** `alpha === 255` (fully opaque)

There are no semi-transparent pixels; every pixel is either fully on or fully
off. Use `getBuffer()` to read all 64 × 64 × 4 bytes in one call, then check
the alpha channel (index `i+3`) to determine membership:

```ts
const buf = window.pixelEditorApi.getBuffer(); // Uint8ClampedArray, 16 384 bytes
const SIZE = 64;

// Collect all opaque (character) pixel coordinates
const characterPixels: Array<[number, number]> = [];
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const alpha = buf[(y * SIZE + x) * 4 + 3];
    if (alpha > 0) characterPixels.push([x, y]);
  }
}

// Compute axis-aligned bounding box of the character
const xs = characterPixels.map(([x]) => x);
const ys = characterPixels.map(([, y]) => y);
const bbox = {
  minX: Math.min(...xs), maxX: Math.max(...xs),
  minY: Math.min(...ys), maxY: Math.max(...ys),
};
// bbox gives the tight rectangle that contains the entire character
```

### Applying spatial transforms to grot

When performing transforms (scale, shift, rotate) always:

1. **Snapshot the source first** — read the full buffer before writing any
   pixels, so reads are never contaminated by partial writes.
2. **Fill background with opaque black** — transparent pixels that end up
   outside the character area should be set to `[0, 0, 0, 255]` so the LED
   display renders a black background instead of undefined colour.
3. **Write all pixels in a second pass** — collect the full list of
   `[x, y, color]` tuples, then apply them with `setPixel` in one loop.

Example — scale the character to 80 % centred on a black canvas:

```ts
const buf = window.pixelEditorApi.getBuffer();
const SIZE = 64;
const SCALE = 0.8;
const newSize = Math.round(SIZE * SCALE);          // 51
const ox = Math.floor((SIZE - newSize) / 2);       // 6  (left/top offset)
const oy = ox;                                       // same for y (centered)

const pixels: Array<[number, number, [number, number, number, number]]> = [];
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const dx = x - ox, dy = y - oy;
    let c: [number, number, number, number];
    if (dx >= 0 && dx < newSize && dy >= 0 && dy < newSize) {
      const srcX = Math.min(Math.floor(dx / SCALE), SIZE - 1);
      const srcY = Math.min(Math.floor(dy / SCALE), SIZE - 1);
      const i = (srcY * SIZE + srcX) * 4;
      // Transparent source pixels become black background
      c = buf[i + 3] === 0
        ? [0, 0, 0, 255]
        : [buf[i], buf[i + 1], buf[i + 2], 255];
    } else {
      c = [0, 0, 0, 255]; // outside scaled area → black
    }
    pixels.push([x, y, c]);
  }
}
for (const [x, y, c] of pixels) window.pixelEditorApi.setPixel(x, y, c);
```

### Agent workflow: edit grot via `javascript:` URL navigation

When the browser automation tool does **not** expose a JS evaluation primitive
(e.g. cursor-ide-browser MCP), use `javascript:` URL navigation instead:

```
browser_navigate(url="javascript:(<your minified IIFE here>)")
```

The page stays at `http://localhost:5174/` and the script runs in page context.
Use an immediately-invoked async arrow for async work:

```
javascript:(async()=>{ /* ... await api calls ... */ })();
```

To **read back** a value from the page after executing JS, inject a hidden
`<textarea>` and read its value with `browser_get_input_value`:

```javascript
// Write side (inside javascript: URL):
let ta = document.getElementById('_out');
if (!ta) { ta = document.createElement('textarea'); ta.id = '_out';
           ta.style.cssText = 'position:fixed;left:-9999px';
           document.body.appendChild(ta); }
ta.value = myValue;

// Read side (browser tool call):
browser_get_input_value(selector="#_out")
```

This technique is used to extract the exported PNG as a base64 string:

```javascript
// Inside javascript: URL
(async () => {
  const blob = await window.pixelEditorApi.exportPngBlob();
  const ab   = await blob.arrayBuffer();
  const b64  = btoa(String.fromCharCode(...new Uint8Array(ab)));
  let ta = document.getElementById('_export_ta');
  if (!ta) { ta = document.createElement('textarea'); ta.id = '_export_ta';
             ta.style.cssText = 'position:fixed;left:-9999px';
             document.body.appendChild(ta); }
  ta.value = b64;
})();
```

Then decode and save from the host shell:

```python
import base64, pathlib
b64 = "<value from browser_get_input_value>"
pathlib.Path("output.png").write_bytes(base64.b64decode(b64))
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

### Option 3: Direct filesystem export (dev mode only)

Save a PNG directly to the host filesystem without dialogs or base64 encoding.
The path must be absolute and within the repository root.

Playwright-style:

```ts
await page.evaluate(async () => {
  await window.pixelEditorApi!.exportPngBlobToPath('/absolute/path/to/output.png');
});
```

Via `javascript:` URL navigation (cursor-ide-browser MCP):

```
javascript:void(window.pixelEditorApi.exportPngBlobToPath('/absolute/path/to/output.png'))
```

This is the recommended export method for agents — it eliminates the base64
textarea workaround described in the `javascript:` URL section above.

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

