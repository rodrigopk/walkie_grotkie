"""Sprite loading and frame rendering for pixel-art animations.

Provides the Sprite class for extracting character pixels from a PNG
(using alpha transparency) and rendering transformed frames suitable
for animated GIF generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

GROT_PNG = Path(__file__).resolve().parents[2] / "pixel-art-editor" / "public" / "grot.png"


@dataclass
class Sprite:
    """Character pixels extracted from a PNG with alpha transparency.

    Attributes:
        pixels: List of (x, y, (r, g, b, a)) tuples for opaque pixels.
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        bbox: Tight bounding box as (min_x, min_y, max_x, max_y).
        center_x: Horizontal center of the bounding box.
        center_y: Vertical center of the bounding box.
    """

    pixels: list[tuple[int, int, tuple[int, int, int, int]]]
    width: int
    height: int
    bbox: tuple[int, int, int, int]
    center_x: float
    center_y: float

    @classmethod
    def from_png(cls, path: Path | str) -> Sprite:
        """Load a PNG and extract opaque pixels (alpha > 0).

        Args:
            path: Path to a PNG file with alpha transparency.

        Returns:
            A Sprite instance with all opaque pixels extracted.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the image has no opaque pixels.
        """
        path = Path(path)
        img = Image.open(path).convert("RGBA")
        px = img.load()
        w, h = img.size

        pixels: list[tuple[int, int, tuple[int, int, int, int]]] = []
        min_x, min_y = w, h
        max_x, max_y = -1, -1

        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a > 0:
                    pixels.append((x, y, (r, g, b, a)))
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        if not pixels:
            raise ValueError(f"No opaque pixels found in {path}")

        return cls(
            pixels=pixels,
            width=w,
            height=h,
            bbox=(min_x, min_y, max_x, max_y),
            center_x=(min_x + max_x) / 2.0,
            center_y=(min_y + max_y) / 2.0,
        )

    def render_frame(
        self,
        x_offset: int = 0,
        y_offset: int = 0,
        flip_x: bool = False,
        bg: tuple[int, int, int, int] = (0, 0, 0, 255),
    ) -> Image.Image:
        """Render the sprite onto a new frame with optional transform.

        Args:
            x_offset: Horizontal pixel shift (positive = right).
            y_offset: Vertical pixel shift (positive = down, negative = up).
            flip_x: Mirror the character horizontally around its center_x.
            bg: Background color as (r, g, b, a).

        Returns:
            A new PIL Image with the transformed sprite on the background.
        """
        frame = Image.new("RGBA", (self.width, self.height), bg)
        frame_px = frame.load()

        for x, y, color in self.pixels:
            px = round(2 * self.center_x - x) if flip_x else x
            px += x_offset
            py = y + y_offset

            if 0 <= px < self.width and 0 <= py < self.height:
                frame_px[px, py] = color

        return frame
