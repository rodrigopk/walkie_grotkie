"""GIF validation and preprocessing for iDotMatrix devices.

Validates that input files are proper GIF images and preprocesses them
(resize, optimize palette, strip metadata) for upload to the device.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

logger = logging.getLogger(__name__)

GIF_MAGIC_87A = b"GIF87a"
GIF_MAGIC_89A = b"GIF89a"


class ValidationError(Exception):
    """Raised when one or more GIF files fail validation.

    Attributes:
        errors: List of (path, error_message) tuples for each failure.
    """

    def __init__(self, errors: list[tuple[Path, str]]) -> None:
        self.errors = errors
        file_list = "\n".join(f"  {p}: {msg}" for p, msg in errors)
        super().__init__(f"Validation failed for {len(errors)} file(s):\n{file_list}")


@dataclass
class PreprocessResult:
    """Result of preprocessing a single GIF file."""

    input_path: Path
    output_path: Path
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    original_bytes: int
    output_bytes: int
    frame_count: int


def validate_gif(file_path: Path) -> None:
    """Validate that a file is a proper GIF image.

    Args:
        file_path: Path to the file to validate.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a valid GIF.
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}. Check the path and try again."
        )

    with open(file_path, "rb") as f:
        magic = f.read(6)

    if magic not in (GIF_MAGIC_87A, GIF_MAGIC_89A):
        raise ValueError(
            f"Not a valid GIF file: {file_path}. "
            f"Expected GIF87a/GIF89a header, got {magic!r}."
        )

    try:
        with Image.open(file_path) as img:
            if img.format != "GIF":
                raise ValueError(
                    f"Pillow does not recognize {file_path} as a GIF (format={img.format!r})."
                )
            frame_count = sum(1 for _ in ImageSequence.Iterator(img))
            if frame_count < 1:
                raise ValueError(f"GIF has no frames: {file_path}.")
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Cannot open GIF file {file_path}: {exc}") from exc


def preprocess_gif(
    input_path: Path,
    output_dir: Path,
    target_size: tuple[int, int] = (32, 32),
    optimize: bool = True,
) -> PreprocessResult:
    """Preprocess a single GIF for iDotMatrix upload.

    Resizes frames if needed, optimizes palette, and strips metadata.

    Args:
        input_path: Path to the source GIF.
        output_dir: Directory to write the processed GIF into.
        target_size: Target resolution (width, height).
        optimize: Whether to optimize the output.

    Returns:
        PreprocessResult with before/after stats.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / input_path.name

    original_bytes = input_path.stat().st_size

    with Image.open(input_path) as img:
        original_size = img.size
        duration = img.info.get("duration", 100)

        frames: list[Image.Image] = []
        for frame in ImageSequence.Iterator(img):
            rgba = frame.convert("RGBA")
            if rgba.size != target_size:
                rgba = rgba.resize(target_size, Image.Resampling.NEAREST)
            rgb = rgba.convert("RGB")
            quantized = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
            frames.append(quantized)

    gif_buffer = io.BytesIO()
    frames[0].save(
        gif_buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=optimize,
    )

    output_path.write_bytes(gif_buffer.getvalue())
    output_bytes = output_path.stat().st_size

    logger.info(
        "Preprocessed %s -> %s (%s -> %s, %d -> %d bytes, %d frames)",
        input_path,
        output_path,
        f"{original_size[0]}x{original_size[1]}",
        f"{target_size[0]}x{target_size[1]}",
        original_bytes,
        output_bytes,
        len(frames),
    )

    return PreprocessResult(
        input_path=input_path,
        output_path=output_path,
        original_size=original_size,
        output_size=target_size,
        original_bytes=original_bytes,
        output_bytes=output_bytes,
        frame_count=len(frames),
    )


def preprocess_batch(
    input_paths: list[Path],
    output_dir: Path,
    target_size: tuple[int, int] = (32, 32),
    optimize: bool = True,
) -> list[PreprocessResult]:
    """Validate and preprocess a batch of GIF files.

    Validates ALL files before processing ANY. If any file fails validation,
    a ValidationError is raised listing every failure — no files are processed.

    Args:
        input_paths: List of GIF file paths to process.
        output_dir: Directory to write processed GIFs into.
        target_size: Target resolution (width, height).
        optimize: Whether to optimize the output.

    Returns:
        List of PreprocessResult, one per input file.

    Raises:
        ValidationError: If any input file fails validation (lists all failures).
    """
    errors: list[tuple[Path, str]] = []
    for path in input_paths:
        try:
            validate_gif(path)
        except (ValueError, FileNotFoundError) as exc:
            errors.append((path, str(exc)))

    if errors:
        raise ValidationError(errors)

    results: list[PreprocessResult] = []
    for path in input_paths:
        result = preprocess_gif(path, output_dir, target_size, optimize)
        results.append(result)

    return results
