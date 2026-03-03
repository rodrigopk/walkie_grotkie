"""Upload orchestration for iDotMatrix devices.

Ties together preprocessing and the DeviceService for BLE transfer
with progress reporting.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import ble, protocol
from .preprocess import preprocess_batch
from .service import DeviceService, UploadError

logger = logging.getLogger(__name__)

__all__ = ["UploadError", "upload_gifs"]


async def upload_gifs(
    gif_paths: list[Path],
    device_address: str | None = None,
    device_name_prefix: str = ble.DEVICE_NAME_PREFIX,
    target_size: tuple[int, int] = (32, 32),
    chunk_size: int = protocol.DEFAULT_CHUNK_SIZE,
    ack_timeout: float = 5.0,
    max_retries: int = 3,
    on_progress: Callable[[int, int, int, int], None] | None = None,
    preprocess: bool = True,
    preprocessed_dir: Path | None = None,
    upload_delay: float | None = None,
    use_cache: bool = True,
) -> None:
    """Preprocess and upload one or more GIFs to an iDotMatrix device.

    Args:
        gif_paths: Paths to GIF files to upload.
        device_address: BLE address (if None, tries cache then scans).
        device_name_prefix: Name prefix for scanning.
        target_size: Target resolution for preprocessing.
        chunk_size: Protocol-level chunk size in bytes.
        ack_timeout: Seconds to wait for each ACK notification.
        max_retries: Max retry attempts per chunk on ACK timeout.
        on_progress: Callback(file_idx, total_files, chunk_idx, total_chunks).
        preprocess: Whether to preprocess GIFs before upload.
        preprocessed_dir: Directory for preprocessed files (temp dir if None).
        upload_delay: Seconds to wait between successive GIF uploads.
        use_cache: Try cached device addresses before scanning.

    Raises:
        UploadError: If a chunk fails after max_retries.
        preprocess.ValidationError: If any input file fails validation.
        ble.BLEConnectionError: If device connection fails.
    """
    if not gif_paths:
        logger.warning("No GIF files to upload")
        return

    upload_paths = list(gif_paths)

    if preprocess:
        if preprocessed_dir is None:
            _tmpdir = tempfile.mkdtemp(prefix="idotmatrix_")
            preprocessed_dir = Path(_tmpdir)
        logger.info("Preprocessing %d GIF(s)...", len(gif_paths))
        results = preprocess_batch(upload_paths, preprocessed_dir, target_size)
        upload_paths = [r.output_path for r in results]
        logger.info("Preprocessing complete")

    async with DeviceService(
        device_address=device_address,
        device_name_prefix=device_name_prefix,
        ack_timeout=ack_timeout,
        max_retries=max_retries,
        use_cache=use_cache,
    ) as device:
        total_files = len(upload_paths)
        for file_idx, gif_path in enumerate(upload_paths):
            logger.info(
                "Uploading file %d/%d: %s",
                file_idx + 1,
                total_files,
                gif_path.name,
            )
            gif_data = gif_path.read_bytes()

            def _file_progress(chunk_idx: int, total_chunks: int) -> None:
                if on_progress is not None:
                    on_progress(file_idx, total_files, chunk_idx, total_chunks)

            await device.upload_gif(
                gif_data,
                chunk_size=chunk_size,
                on_progress=_file_progress,
            )

            logger.info("Finished uploading %s", gif_path.name)

            if upload_delay is not None and file_idx < total_files - 1:
                logger.info("Waiting %.1fs before next upload...", upload_delay)
                await asyncio.sleep(upload_delay)
