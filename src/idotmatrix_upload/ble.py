"""BLE connection layer for iDotMatrix devices.

Handles scanning, connecting, MTU negotiation, notification subscription,
and data writing via bleak.
"""

from __future__ import annotations

import asyncio
import logging
import platform
from collections.abc import Awaitable, Callable
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

logger = logging.getLogger(__name__)

SERVICE_UUID = "000000fa-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"
DEVICE_NAME_PREFIX = "IDM-"

DEFAULT_MTU = 23


class BLEConnectionError(Exception):
    """Raised when a BLE connection cannot be established."""


class BLEWriteError(Exception):
    """Raised when a BLE write operation fails."""


class DeviceConnection:
    """Wraps a BleakClient with iDotMatrix-specific write/disconnect methods."""

    def __init__(self, client: BleakClient, mtu_size: int) -> None:
        self._client = client
        self.address: str = client.address
        self.mtu_size: int = mtu_size

    async def write(self, data: bytes) -> None:
        """Write data to the device write characteristic.

        Sub-chunks the data into BLE-level writes of (MTU - 3) bytes.
        Uses write-without-response for speed.

        Args:
            data: The bytes to write (typically a full protocol packet).

        Raises:
            BLEWriteError: If the write fails.
        """
        chunk_size = max(self.mtu_size - 3, 20)
        try:
            for i in range(0, len(data), chunk_size):
                chunk = data[i : i + chunk_size]
                await self._client.write_gatt_char(
                    WRITE_UUID, chunk, response=False
                )
        except (BleakError, OSError) as exc:
            raise BLEWriteError(
                f"Failed to write to device {self.address}: {exc}. "
                f"Make sure the device is still connected and in range."
            ) from exc

    async def disconnect(self) -> None:
        """Disconnect from the device. Safe to call multiple times."""
        try:
            if self._client.is_connected:
                await self._client.disconnect()
                logger.info("Disconnected from %s", self.address)
        except (BleakError, OSError) as exc:
            logger.debug("Error during disconnect from %s: %s", self.address, exc)


async def scan(
    name_prefix: str = DEVICE_NAME_PREFIX,
    timeout: float = 10.0,
) -> list[str]:
    """Scan for iDotMatrix devices.

    Args:
        name_prefix: BLE local name prefix to filter on.
        timeout: How long to scan in seconds.

    Returns:
        List of BLE addresses for matching devices.

    Raises:
        BLEConnectionError: If scanning fails.
    """
    logger.info("Scanning for devices with prefix '%s' (%.1fs)...", name_prefix, timeout)
    try:
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    except (BleakError, OSError) as exc:
        raise BLEConnectionError(
            f"BLE scan failed: {exc}. "
            f"Make sure Bluetooth is enabled on this computer."
        ) from exc

    matches: list[str] = []
    for _key, (device, adv) in devices.items():
        if (
            isinstance(adv, AdvertisementData)
            and adv.local_name
            and adv.local_name.startswith(name_prefix)
        ):
            logger.info("Found device: %s (%s)", adv.local_name, device.address)
            matches.append(device.address)

    return matches


async def connect(
    address: str,
    timeout: float = 10.0,
    on_notification: Optional[Callable[[bytes], Awaitable[None] | None]] = None,
) -> DeviceConnection:
    """Connect to an iDotMatrix device.

    Args:
        address: BLE address to connect to.
        timeout: Connection timeout in seconds.
        on_notification: Async or sync callback for notifications on NOTIFY_UUID.

    Returns:
        A connected DeviceConnection.

    Raises:
        BLEConnectionError: If connection or setup fails.
    """
    logger.info("Connecting to %s...", address)
    try:
        client = BleakClient(address, timeout=timeout)
        await client.connect()
    except (BleakError, asyncio.TimeoutError, OSError) as exc:
        raise BLEConnectionError(
            f"Could not connect to device {address}: {exc}. "
            f"Make sure the device is powered on and within BLE range, then retry."
        ) from exc

    mtu = DEFAULT_MTU
    try:
        if platform.system() == "Linux":
            await client._backend._acquire_mtu()  # type: ignore[attr-defined]
        mtu = client.mtu_size
        logger.info("Negotiated MTU: %d", mtu)
    except Exception:
        logger.debug("MTU negotiation failed, using default %d", DEFAULT_MTU)

    if on_notification is not None:
        try:
            def _notification_handler(_sender: int, data: bytearray) -> None:
                result = on_notification(bytes(data))
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)

            await client.start_notify(NOTIFY_UUID, _notification_handler)
            logger.info("Subscribed to notifications on %s", NOTIFY_UUID)
        except (BleakError, OSError) as exc:
            await client.disconnect()
            raise BLEConnectionError(
                f"Failed to subscribe to notifications on {address}: {exc}."
            ) from exc

    return DeviceConnection(client, mtu)
