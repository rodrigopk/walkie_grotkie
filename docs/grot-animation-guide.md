# Grot Animation & Drawing Guide

This document covers how to draw, manipulate, and animate the **grot**
character — both via Python scripts (recommended) and through the browser-based
pixel editor.

## Grot Character Basics

### Alpha transparency

The grot image uses alpha transparency to separate character pixels from the
background:

- **Background pixels:** `alpha === 0` (fully transparent `[r, g, b, 0]`)
- **Character pixels:** `alpha === 255` (fully opaque)

There are no semi-transparent pixels; every pixel is either fully on or fully
off.

### Bounding box and center

When loaded via `Sprite.from_png()`, the bounding box (`bbox`) and center
(`center_x`, `center_y`) are computed automatically from opaque pixels. These
values drive transforms like flipping and centering.

---

## Python-First Animation (Recommended)

The recommended way to generate animated GIFs is with a **Python script** using
the `Sprite` helper class and `assemble_gif_from_frames`. No browser or dev
server required — the agent writes a short Python script, runs it, and gets
both the frame PNGs and the assembled GIF.

### Architecture overview

1. Agent writes a Python script.
2. Script uses `Sprite.from_png(GROT_PNG)` to load the base image.
3. Script loops over frames, calling `sprite.render_frame(...)` with per-frame
   transforms, saving each frame as a PNG.
4. Script calls `assemble_gif_from_frames(...)` to combine frames into a GIF.

### Key imports

```python
import math
from pathlib import Path
from walkie_grotkie.sprite import Sprite, GROT_PNG
from walkie_grotkie.generate import assemble_gif_from_frames
```

- `Sprite.from_png(path)` — loads a PNG, extracts opaque pixels (alpha > 0),
  computes bounding box and center coordinates.
- `sprite.render_frame(x_offset, y_offset, flip_x, bg)` — renders the sprite
  onto a new PIL Image with the given transform. Returns the Image directly.
- `GROT_PNG` — `Path` to `pixel-art-editor/public/grot.png`.
- `assemble_gif_from_frames(paths, output, fps, loop, size)` — combines sorted
  PNG files into an animated GIF using Pillow.

### `Sprite` API reference

```python
@dataclass
class Sprite:
    pixels: list[tuple[int, int, tuple[int, int, int, int]]]  # (x, y, rgba)
    width: int                    # canvas width
    height: int                   # canvas height
    bbox: tuple[int, int, int, int]  # (min_x, min_y, max_x, max_y)
    center_x: float               # horizontal center of bounding box
    center_y: float               # vertical center of bounding box

    @classmethod
    def from_png(cls, path: Path | str) -> Sprite: ...

    def render_frame(
        self,
        x_offset: int = 0,          # horizontal shift (positive = right)
        y_offset: int = 0,          # vertical shift (positive = down)
        flip_x: bool = False,       # mirror horizontally around center_x
        bg: tuple[int, int, int, int] = (0, 0, 0, 255),
    ) -> Image.Image: ...
```

### Planning animation parameters

Given a prompt like *"1.8 seconds at 20 fps"*, derive:

```python
duration_s = 1.8
fps = 20
total_frames = math.ceil(duration_s * fps)   # 36
frames_per_cycle = total_frames // num_cycles
```

### Common transform recipes

**Vertical translation (jump)**

```python
jump_phase = (f % frames_per_jump) / frames_per_jump
y_offset = -round(math.sin(jump_phase * math.pi) * JUMP_HEIGHT)
```

**Horizontal translation (slide/walk)**

```python
t = f / total_frames
x_offset = round(math.sin(t * 2 * math.pi) * SLIDE_DISTANCE)
```

**Horizontal flip (face other direction)**

```python
flip = (f // frames_per_jump) % 2 == 1
frame = sprite.render_frame(y_offset=y_offset, flip_x=flip)
```

**Easing (smooth start/stop)**

```python
def ease_in_out(t: float) -> float:
    return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2

y_offset = -round(ease_in_out(jump_phase) * JUMP_HEIGHT)
```

### GIF assembly

**Option A — direct Python call** (recommended when the script generates the frames):

```python
from walkie_grotkie.generate import assemble_gif_from_frames

frame_paths = sorted(frames_dir.glob("*.png"))
assemble_gif_from_frames(frame_paths, Path("output/animation.gif"), fps=20)
```

**Option B — CLI** (useful when frames already exist on disk):

```bash
walkie-grotkie assemble-gif ./frames -o animation.gif --fps 20
```

Options: `-o` (required) output path, `--fps` (default 20), `--loop` (default
0 = infinite), `--size` optional resize e.g. `32x32`.

### Complete worked example: grot jump-and-flip

Prompt: *"Generate an animation of grot jumping 4 times, flipping
horizontally on each landing. 2 seconds at 20 fps."*

```python
import math
from pathlib import Path
from walkie_grotkie.sprite import Sprite, GROT_PNG
from walkie_grotkie.generate import assemble_gif_from_frames

sprite = Sprite.from_png(GROT_PNG)
frames_dir = Path("output/grot-jump-flip/frames")
frames_dir.mkdir(parents=True, exist_ok=True)

FRAMES, JUMPS, HEIGHT = 40, 4, 14
FRAMES_PER_JUMP = FRAMES // JUMPS

for f in range(FRAMES):
    phase = (f % FRAMES_PER_JUMP) / FRAMES_PER_JUMP
    y_off = -round(math.sin(phase * math.pi) * HEIGHT)
    flip = (f // FRAMES_PER_JUMP) % 2 == 1

    sprite.render_frame(y_offset=y_off, flip_x=flip).save(
        frames_dir / f"frame_{f:03d}.png"
    )

assemble_gif_from_frames(
    sorted(frames_dir.glob("*.png")),
    Path("output/grot-jump-flip/grot-jump-flip.gif"),
    fps=20,
)
```

Run with: `python3 scripts/my_animation.py`

Optionally resize for iDotMatrix upload:

```bash
walkie-grotkie assemble-gif output/grot-jump-flip/frames \
  -o output/grot-jump-flip/grot-32.gif --fps 20 --size 32x32
walkie-grotkie upload output/grot-jump-flip/grot-32.gif
```

---

## Browser-Based Drawing & Frame Generation (Alternative)

Use this path when you are already in the pixel editor doing interactive edits
and want to generate frames from the current canvas state. It requires the dev
server to be running (`npm run dev` in `pixel-art-editor/`).

### Loading grot in the pixel editor

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

### Identifying the character outline via API

Use `getBuffer()` to read all 64 × 64 × 4 bytes in one call, then check
the alpha channel (index `i+3`) to determine membership:

```ts
const buf = window.pixelEditorApi.getBuffer(); // Uint8ClampedArray, 16 384 bytes
const SIZE = 64;

const characterPixels: Array<[number, number]> = [];
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const alpha = buf[(y * SIZE + x) * 4 + 3];
    if (alpha > 0) characterPixels.push([x, y]);
  }
}

const xs = characterPixels.map(([x]) => x);
const ys = characterPixels.map(([, y]) => y);
const bbox = {
  minX: Math.min(...xs), maxX: Math.max(...xs),
  minY: Math.min(...ys), maxY: Math.max(...ys),
};
```

### Spatial transforms via API

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
const oy = ox;

const pixels: Array<[number, number, [number, number, number, number]]> = [];
for (let y = 0; y < SIZE; y++) {
  for (let x = 0; x < SIZE; x++) {
    const dx = x - ox, dy = y - oy;
    let c: [number, number, number, number];
    if (dx >= 0 && dx < newSize && dy >= 0 && dy < newSize) {
      const srcX = Math.min(Math.floor(dx / SCALE), SIZE - 1);
      const srcY = Math.min(Math.floor(dy / SCALE), SIZE - 1);
      const i = (srcY * SIZE + srcX) * 4;
      c = buf[i + 3] === 0
        ? [0, 0, 0, 255]
        : [buf[i], buf[i + 1], buf[i + 2], 255];
    } else {
      c = [0, 0, 0, 255];
    }
    pixels.push([x, y, c]);
  }
}
for (const [x, y, c] of pixels) window.pixelEditorApi.setPixel(x, y, c);
```

### Using `setBuffer` for bulk updates

`setBuffer` replaces all 16,384 bytes at once — use it instead of per-pixel
loops when updating the entire canvas (e.g. animation frames). It intentionally
skips undo history. Snapshot the base buffer with `getBuffer()` before calling
it if you need to restore later.

### Generating frames from the browser

Use `setBuffer` + `exportPngBlobToPath` in a loop to generate animation frames
from the pixel editor. See the `setBuffer` and `exportPngBlobToPath` methods in
the `window.pixelEditorApi` contract documented in
`pixel-art-editor/AGENTS.md`.

### Agent workflow: `javascript:` URL navigation

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

The `exportPngBlobToPath` API is a simpler alternative — it writes the PNG
directly to the host filesystem without base64 encoding:

```
javascript:void(window.pixelEditorApi.exportPngBlobToPath('/absolute/path/to/output.png'))
```
