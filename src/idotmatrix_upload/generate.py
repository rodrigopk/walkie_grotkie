"""Generate test GIF animations for iDotMatrix devices.

Creates animated GIFs showing numbers spinning 360 degrees counter-clockwise,
with yellow text on a black background, sized for iDotMatrix LED matrices.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def _render_digit(
    number: int,
    size: int,
    font_color: tuple[int, int, int],
    bg_color: tuple[int, int, int],
) -> Image.Image:
    """Render a number centered on a square RGBA canvas."""
    img = Image.new("RGBA", (size, size), (*bg_color, 255))
    draw = ImageDraw.Draw(img)

    text = str(number)

    font_size = int(size * 0.85)
    try:
        font = ImageFont.load_default(size=font_size)
    except TypeError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]

    draw.text((x, y), text, fill=(*font_color, 255), font=font)
    return img


def generate_spinning_number_gif(
    number: int,
    output_path: Path,
    size: int = 32,
    num_frames: int = 36,
    frame_duration_ms: int = 50,
    font_color: tuple[int, int, int] = (255, 255, 0),
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> Path:
    """Generate a single animated GIF of a spinning number.

    The number rotates 360 degrees counter-clockwise over num_frames frames.

    Args:
        number: The number to display (e.g. 1-10).
        output_path: Where to save the GIF.
        size: Pixel dimension (width = height).
        num_frames: Total animation frames.
        frame_duration_ms: Duration of each frame in milliseconds.
        font_color: RGB tuple for the digit color.
        bg_color: RGB tuple for the background.

    Returns:
        The output path.
    """
    base = _render_digit(number, size, font_color, bg_color)

    frames: list[Image.Image] = []
    angle_step = 360.0 / num_frames

    for i in range(num_frames):
        angle = i * angle_step
        rotated = base.rotate(
            angle,
            resample=Image.Resampling.NEAREST,
            expand=False,
            fillcolor=(*bg_color, 255),
        )
        frame = Image.new("P", (size, size))
        rgb = rotated.convert("RGB")
        quantized = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        frames.append(quantized)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        disposal=2,
    )

    logger.info("Generated %s (%d bytes, %d frames)", output_path, output_path.stat().st_size, num_frames)
    return output_path


def generate_test_set(
    output_dir: Path,
    count: int = 10,
    size: int = 32,
) -> list[Path]:
    """Generate a set of spinning number GIFs (1 through count).

    Args:
        output_dir: Directory to write GIF files into.
        count: How many GIFs to generate (1..count).
        size: Pixel dimension for each GIF.

    Returns:
        List of paths to the generated GIF files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for n in range(1, count + 1):
        filename = f"number_{n:02d}.gif"
        path = generate_spinning_number_gif(n, output_dir / filename, size=size)
        paths.append(path)

    logger.info("Generated %d test GIFs in %s", count, output_dir)
    return paths
