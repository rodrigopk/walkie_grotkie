"""BLE Explorer for iDotMatrix devices.

Connects to the device and enumerates all GATT services, characteristics,
and descriptors. Attempts to read any readable characteristics and logs
everything for reverse-engineering purposes.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEVICE_NAME_PREFIX = "IDM-"
KNOWN_WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
KNOWN_NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

PROPERTY_NAMES = {
    "read": "READ",
    "write": "WRITE",
    "write-without-response": "WRITE_NO_RESP",
    "notify": "NOTIFY",
    "indicate": "INDICATE",
    "broadcast": "BROADCAST",
    "authenticated-signed-writes": "AUTH_SIGNED",
    "extended-properties": "EXTENDED",
}


def format_properties(props: list[str]) -> str:
    return " | ".join(PROPERTY_NAMES.get(p, p.upper()) for p in props)


async def scan_for_device() -> str | None:
    logger.info("Scanning for iDotMatrix devices...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    for _key, (device, adv) in devices.items():
        if (
            isinstance(adv, AdvertisementData)
            and adv.local_name
            and adv.local_name.startswith(DEVICE_NAME_PREFIX)
        ):
            logger.info("  Found: %s (%s) RSSI=%s", adv.local_name, device.address, adv.rssi)
            return device.address

    return None


async def explore_device(address: str) -> None:
    logger.info("\nConnecting to %s...", address)
    async with BleakClient(address, timeout=15.0) as client:
        logger.info("Connected! MTU: %d\n", client.mtu_size)
        logger.info("=" * 72)
        logger.info("GATT SERVICE TABLE")
        logger.info("=" * 72)

        for service in client.services:
            known_tag = ""
            logger.info("\nService: %s", service.uuid)
            logger.info("  Description: %s", service.description or "(unknown)")
            logger.info("  Handle: 0x%04X", service.handle)

            for char in service.characteristics:
                props = format_properties(char.properties)

                if char.uuid == KNOWN_WRITE_UUID:
                    known_tag = "  <-- KNOWN: write data"
                elif char.uuid == KNOWN_NOTIFY_UUID:
                    known_tag = "  <-- KNOWN: notify/read"
                else:
                    known_tag = "  *** UNKNOWN - INVESTIGATE ***"

                logger.info(
                    "  Characteristic: %s%s",
                    char.uuid,
                    known_tag,
                )
                logger.info("    Handle: 0x%04X", char.handle)
                logger.info("    Properties: %s", props)

                for desc in char.descriptors:
                    logger.info("    Descriptor: %s (0x%04X)", desc.uuid, desc.handle)
                    if desc.uuid == CCCD_UUID:
                        logger.info("      (CCCD — skipped, managed by OS on macOS)")
                        continue
                    try:
                        val = await client.read_gatt_descriptor(desc.handle)
                        logger.info("      Value: %s", val.hex())
                    except Exception as exc:
                        logger.info("      Read failed: %s", exc)

                if "read" in char.properties:
                    try:
                        data = await client.read_gatt_char(char.uuid)
                        logger.info("    READ value: %s", data.hex())
                        if len(data) > 0:
                            logger.info("    READ ascii: %s", data.decode("ascii", errors="replace"))
                    except Exception as exc:
                        logger.info("    READ failed: %s", exc)

        logger.info("\n" + "=" * 72)
        logger.info("NOTIFICATION PROBE")
        logger.info("=" * 72)

        notifications: list[tuple[str, bytes]] = []

        def make_handler(uuid: str):
            def handler(_sender: int, data: bytearray) -> None:
                notifications.append((uuid, bytes(data)))
                logger.info("  Notification from %s: %s", uuid, bytes(data).hex())
            return handler

        notify_chars = []
        for service in client.services:
            for char in service.characteristics:
                if "notify" in char.properties or "indicate" in char.properties:
                    notify_chars.append(char)

        for char in notify_chars:
            try:
                await client.start_notify(char.uuid, make_handler(char.uuid))
                logger.info("Subscribed to notifications on %s", char.uuid)
            except Exception as exc:
                logger.info("Could not subscribe to %s: %s", char.uuid, exc)

        if notify_chars:
            logger.info("\nListening for unsolicited notifications for 5 seconds...")
            await asyncio.sleep(5)

        logger.info("\n" + "=" * 72)
        logger.info("COMMAND PROBE (sending known status commands)")
        logger.info("=" * 72)

        probe_commands = [
            ("Device info query (guess: 05 00 04 01 00)", bytes([0x05, 0x00, 0x04, 0x01, 0x00])),
            ("Device info query (guess: 05 00 04 00 00)", bytes([0x05, 0x00, 0x04, 0x00, 0x00])),
            ("Version query (guess: 05 00 08 01 00)", bytes([0x05, 0x00, 0x08, 0x01, 0x00])),
            ("Flash info (guess: 05 00 09 01 00)", bytes([0x05, 0x00, 0x09, 0x01, 0x00])),
            ("Storage query (guess: 05 00 0a 01 00)", bytes([0x05, 0x00, 0x0a, 0x01, 0x00])),
        ]

        for label, cmd in probe_commands:
            notifications.clear()
            try:
                logger.info("\nSending: %s -> %s", label, cmd.hex())
                await client.write_gatt_char(KNOWN_WRITE_UUID, cmd, response=False)
                await asyncio.sleep(1.0)
                if notifications:
                    for uuid, data in notifications:
                        logger.info("  Response: %s", data.hex())
                else:
                    logger.info("  No response received")
            except Exception as exc:
                logger.info("  Write failed: %s", exc)

        for char in notify_chars:
            try:
                await client.stop_notify(char.uuid)
            except Exception:
                pass

    logger.info("\nDone. Disconnected.")


async def main() -> None:
    address = None
    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        address = await scan_for_device()

    if not address:
        logger.error("No iDotMatrix device found. Pass BLE address as argument or ensure device is on.")
        sys.exit(1)

    await explore_device(address)


if __name__ == "__main__":
    asyncio.run(main())
