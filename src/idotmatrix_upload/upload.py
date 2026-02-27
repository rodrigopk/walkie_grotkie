"""Upload orchestration for iDotMatrix devices.

Ties together preprocessing, protocol packet construction, and BLE transfer
with notification-based flow control, retries, and progress reporting.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import ble, protocol
from .preprocess import preprocess_batch

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when an upload fails after exhausting retries."""


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
) -> None:
    """Preprocess and upload one or more GIFs to an iDotMatrix device.

    Args:
        gif_paths: Paths to GIF files to upload.
        device_address: BLE address (if None, scans for a device).
        device_name_prefix: Name prefix for scanning.
        target_size: Target resolution for preprocessing.
        chunk_size: Protocol-level chunk size in bytes.
        ack_timeout: Seconds to wait for each ACK notification.
        max_retries: Max retry attempts per chunk on ACK timeout.
        on_progress: Callback(file_idx, total_files, chunk_idx, total_chunks).
        preprocess: Whether to preprocess GIFs before upload.
        preprocessed_dir: Directory for preprocessed files (temp dir if None).

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

    if device_address is None:
        logger.info("No device address specified, scanning...")
        addresses = await ble.scan(name_prefix=device_name_prefix)
        if not addresses:
            raise ble.BLEConnectionError(
                f"No iDotMatrix device found with prefix '{device_name_prefix}'. "
                f"Make sure the device is powered on and within BLE range."
            )
        device_address = addresses[0]
        logger.info("Using device: %s", device_address)

    ack_event = asyncio.Event()
    ack_result: str = ""

    def on_notification(data: bytes) -> None:
        nonlocal ack_result
        ack_result = protocol.parse_ack(data)
        ack_event.set()

    connection = await ble.connect(
        device_address,
        on_notification=on_notification,
    )

    try:
        total_files = len(upload_paths)
        for file_idx, gif_path in enumerate(upload_paths):
            logger.info(
                "Uploading file %d/%d: %s", file_idx + 1, total_files, gif_path.name
            )
            gif_data = gif_path.read_bytes()
            packets = protocol.build_packets(gif_data, chunk_size)
            total_chunks = len(packets)

            for chunk_idx, packet in enumerate(packets):
                for attempt in range(1, max_retries + 1):
                    ack_event.clear()
                    await connection.write(packet)

                    try:
                        await asyncio.wait_for(
                            ack_event.wait(), timeout=ack_timeout
                        )
                    except asyncio.TimeoutError:
                        if attempt < max_retries:
                            logger.warning(
                                "ACK timeout on chunk %d/%d (attempt %d/%d), retrying...",
                                chunk_idx + 1,
                                total_chunks,
                                attempt,
                                max_retries,
                            )
                            continue
                        raise UploadError(
                            f"Chunk {chunk_idx + 1}/{total_chunks} of {gif_path.name} "
                            f"failed after {max_retries} retries. "
                            f"The device may be out of range or unresponsive."
                        )

                    if ack_result == "complete":
                        logger.info("Device signaled upload complete")
                    break

                if on_progress is not None:
                    on_progress(file_idx, total_files, chunk_idx, total_chunks)

            logger.info("Finished uploading %s", gif_path.name)
    finally:
        await connection.disconnect()
