"""Long-lived device service for iDotMatrix BLE communication.

Encapsulates device discovery, BLE connection lifecycle, ACK-based flow
control, and retry logic.  Consumers use ``DeviceService`` as an async
context manager and call high-level methods like ``upload_gif`` without
managing connection state themselves.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Self

from . import ble, protocol
from .device_cache import add_to_cache, load_cache

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when an upload fails after exhausting retries."""


class DeviceService:
    """Manages a persistent BLE connection to an iDotMatrix device."""

    def __init__(
        self,
        device_address: str | None = None,
        device_name_prefix: str = ble.DEVICE_NAME_PREFIX,
        ack_timeout: float = 5.0,
        max_retries: int = 3,
        use_cache: bool = True,
    ) -> None:
        self._device_address = device_address
        self._device_name_prefix = device_name_prefix
        self._ack_timeout = ack_timeout
        self._max_retries = max_retries
        self._use_cache = use_cache

        self._connection: ble.DeviceConnection | None = None
        self._ack_event = asyncio.Event()
        self._ack_result: str = ""

    # -- Properties ----------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def address(self) -> str | None:
        if self._connection is not None:
            return self._connection.address
        return self._device_address

    # -- Lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        """Resolve the device address and establish a BLE connection.

        Resolution order when no explicit address was provided:
        1. Probe cached addresses for a reachable device (reusing the
           probe connection to avoid a redundant second handshake).
        2. Fall back to a BLE scan filtered by the name prefix.

        Raises:
            ble.BLEConnectionError: If no device can be found or connected to.
        """
        if self._connection is not None:
            return

        address, cached_conn = await self._resolve_device()

        if cached_conn is not None:
            await cached_conn.subscribe_notifications(self._on_notification)
            self._connection = cached_conn
        else:
            self._connection = await ble.connect(
                address,
                on_notification=self._on_notification,
            )

        if self._use_cache:
            add_to_cache(address)

        logger.info("DeviceService connected to %s", address)

    async def disconnect(self) -> None:
        """Disconnect from the device.  Safe to call when not connected."""
        if self._connection is not None:
            await self._connection.disconnect()
            self._connection = None

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.disconnect()

    # -- Operations ----------------------------------------------------------

    async def send_packet(self, packet: bytes) -> str:
        """Send a single protocol packet and wait for the device ACK.

        Retries up to ``max_retries`` on ACK timeout.

        Returns:
            The parsed ACK result (``"ok"``, ``"complete"``, or ``"unknown"``).

        Raises:
            UploadError: If the ACK is not received after all retries.
            RuntimeError: If the service is not connected.
        """
        if self._connection is None:
            raise RuntimeError("DeviceService is not connected")

        for attempt in range(1, self._max_retries + 1):
            self._ack_event.clear()
            await self._connection.write(packet)

            try:
                await asyncio.wait_for(
                    self._ack_event.wait(), timeout=self._ack_timeout
                )
            except asyncio.TimeoutError:
                if attempt < self._max_retries:
                    logger.warning(
                        "ACK timeout (attempt %d/%d), retrying...",
                        attempt,
                        self._max_retries,
                    )
                    continue
                raise UploadError(
                    f"Packet failed after {self._max_retries} retries. "
                    f"The device may be out of range or unresponsive."
                )

            return self._ack_result

        # Unreachable, but keeps the type checker happy.
        raise UploadError("Unexpected retry loop exit")  # pragma: no cover

    async def send_packets(
        self,
        packets: list[bytes],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Send a sequence of protocol packets with ACK flow control.

        Stops immediately when the device sends a ``"complete"`` ACK —
        remaining packets are not sent, matching device protocol expectations.

        Args:
            packets: Ordered list of protocol packets to send.
            on_progress: Optional callback ``(chunk_idx, total_chunks)``.
                         Called after each packet is acknowledged, including
                         the packet that triggers early completion.
        """
        total = len(packets)
        for idx, packet in enumerate(packets):
            result = await self.send_packet(packet)
            if on_progress is not None:
                on_progress(idx, total)
            if result == "complete":
                logger.info("Device signaled upload complete")
                break

    async def upload_gif(
        self,
        gif_data: bytes,
        chunk_size: int = protocol.DEFAULT_CHUNK_SIZE,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        """Build protocol packets from raw GIF bytes and send them.

        Args:
            gif_data: Raw GIF file content.
            chunk_size: Protocol-level chunk size (default 4096).
            on_progress: Optional callback ``(chunk_idx, total_chunks)``.
        """
        packets = protocol.build_packets(gif_data, chunk_size)
        await self.send_packets(packets, on_progress=on_progress)

    # -- Internal ------------------------------------------------------------

    def _on_notification(self, data: bytes) -> None:
        self._ack_result = protocol.parse_ack(data)
        self._ack_event.set()

    async def _resolve_device(self) -> tuple[str, ble.DeviceConnection | None]:
        """Return a usable BLE address via explicit address, cache, or scan.

        Returns:
            A ``(address, connection)`` tuple.  When the address was found via
            the cache, *connection* is the already-open probe connection so the
            caller can reuse it instead of connecting a second time.  In all
            other cases *connection* is ``None``.
        """
        if self._device_address is not None:
            logger.info("Using explicit device address: %s", self._device_address)
            return self._device_address, None

        if self._use_cache:
            cached = load_cache()
            for addr in cached:
                logger.info("Trying cached device %s ...", addr)
                try:
                    probe = await ble.connect(addr, timeout=3.0)
                    logger.info("Cached device %s is reachable", addr)
                    return addr, probe
                except (ble.BLEConnectionError, Exception):
                    logger.debug("Cached device %s unreachable", addr)

        logger.info("Scanning for devices...")
        addresses = await ble.scan(name_prefix=self._device_name_prefix)
        if not addresses:
            raise ble.BLEConnectionError(
                f"No iDotMatrix device found with prefix "
                f"'{self._device_name_prefix}'. "
                f"Make sure the device is powered on and within BLE range."
            )
        return addresses[0], None
