"""CLI entry point for iDotMatrix GIF Upload.

Provides three subcommands:
  - upload:     Preprocess and upload GIFs to a device
  - generate:   Create test GIF animations (spinning numbers)
  - preprocess: Validate and preprocess GIFs for upload
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click

from . import __version__

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def _parse_size(size_str: str) -> tuple[int, int]:
    """Parse a WxH size string into a (width, height) tuple."""
    try:
        parts = size_str.lower().split("x")
        if len(parts) != 2:
            raise ValueError
        return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise click.BadParameter(
            f"Invalid size '{size_str}'. Use WxH format, e.g. 64x64"
        )


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """iDotMatrix GIF Upload — upload GIF animations to iDotMatrix LED matrix devices."""


@main.command()
@click.argument("gif_paths", nargs=-1, required=True, type=click.Path(exists=False))
@click.option("--device-addr", default=None, help="BLE address (skip scan).")
@click.option("--device-name", default="IDM-", help="Device name prefix for scanning.")
@click.option("--size", default="64x64", help="Target resolution WxH.")
@click.option("--chunk-size", default=4096, type=int, help="Bytes per protocol chunk.")
@click.option("--timeout", default=5.0, type=float, help="Per-chunk ACK timeout in seconds.")
@click.option("--no-preprocess", is_flag=True, help="Skip preprocessing.")
@click.option("--delay", default=1.7, type=float, help="Seconds to wait between GIF uploads.")
@click.option("--no-cache", is_flag=True, help="Skip device address cache.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def upload(
    gif_paths: tuple[str, ...],
    device_addr: str | None,
    device_name: str,
    size: str,
    chunk_size: int,
    timeout: float,
    no_preprocess: bool,
    delay: float | None,
    no_cache: bool,
    verbose: bool,
) -> None:
    """Upload one or more GIF files to an iDotMatrix device."""
    _setup_logging(verbose)
    target_size = _parse_size(size)
    paths = [Path(p) for p in gif_paths]

    from .ble import BLEConnectionError
    from .preprocess import ValidationError
    from .upload import UploadError, upload_gifs

    def on_progress(file_idx: int, total_files: int, chunk_idx: int, total_chunks: int) -> None:
        click.echo(
            f"  File {file_idx + 1}/{total_files} — "
            f"chunk {chunk_idx + 1}/{total_chunks}"
        )

    try:
        asyncio.run(
            upload_gifs(
                gif_paths=paths,
                device_address=device_addr,
                device_name_prefix=device_name,
                target_size=target_size,
                chunk_size=chunk_size,
                ack_timeout=timeout,
                preprocess=not no_preprocess,
                on_progress=on_progress,
                upload_delay=delay,
                use_cache=not no_cache,
            )
        )
        click.echo("Upload complete.")
    except ValidationError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except BLEConnectionError as exc:
        click.echo(f"Device error: {exc}", err=True)
        sys.exit(2)
    except UploadError as exc:
        click.echo(f"Upload error: {exc}", err=True)
        sys.exit(2)


@main.command()
@click.option(
    "--output-dir",
    default="./test_gifs",
    type=click.Path(),
    help="Directory to write generated GIFs.",
)
@click.option("--count", default=10, type=int, help="How many GIFs to generate (1..N).")
@click.option("--size", default=64, type=int, help="Pixel dimension (width = height).")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def generate(output_dir: str, count: int, size: int, verbose: bool) -> None:
    """Generate test GIF animations (spinning numbers 1..N)."""
    _setup_logging(verbose)

    from .generate import generate_test_set

    out = Path(output_dir)
    paths = generate_test_set(out, count=count, size=size)
    click.echo(f"Generated {len(paths)} GIF(s) in {out}")
    for p in paths:
        click.echo(f"  {p.name} ({p.stat().st_size} bytes)")


@main.command("assemble-gif")
@click.argument("frames_dir", type=click.Path(exists=True, file_okay=False))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output GIF path.")
@click.option("--fps", default=20, type=int, help="Frames per second.")
@click.option("--loop", default=0, type=int, help="Loop count (0 = infinite).")
@click.option("--size", default=None, help="Optional resize WxH (e.g. 64x64).")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def assemble_gif(
    frames_dir: str, output: str, fps: int, loop: int,
    size: str | None, verbose: bool,
) -> None:
    """Assemble a directory of PNG frames into an animated GIF."""
    _setup_logging(verbose)
    from .generate import assemble_gif_from_frames

    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        raise click.ClickException(f"No PNG files found in {frames_dir}")

    target_size = _parse_size(size) if size else None
    result = assemble_gif_from_frames(
        frames, Path(output), fps=fps, loop=loop, size=target_size,
    )
    click.echo(f"Assembled {len(frames)} frames -> {result} ({result.stat().st_size} bytes)")


@main.command()
@click.argument("gif_paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--output-dir",
    default="./processed",
    type=click.Path(),
    help="Directory for processed GIFs.",
)
@click.option("--size", default="64x64", help="Target resolution WxH.")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def preprocess(gif_paths: tuple[str, ...], output_dir: str, size: str, verbose: bool) -> None:
    """Validate and preprocess GIF files for iDotMatrix upload."""
    _setup_logging(verbose)
    target_size = _parse_size(size)
    paths = [Path(p) for p in gif_paths]

    from .preprocess import ValidationError, preprocess_batch

    try:
        results = preprocess_batch(paths, Path(output_dir), target_size)
        click.echo(f"Preprocessed {len(results)} GIF(s):")
        for r in results:
            click.echo(
                f"  {r.input_path.name}: "
                f"{r.original_size[0]}x{r.original_size[1]} -> "
                f"{r.output_size[0]}x{r.output_size[1]}, "
                f"{r.original_bytes} -> {r.output_bytes} bytes, "
                f"{r.frame_count} frames"
            )
    except ValidationError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
