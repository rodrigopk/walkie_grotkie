"""Probe the iDotMatrix's unknown 0xAE00 service and send test commands.

Discovery from ble_explore.py:
  Service 0x00FA (known):
    0xFA02 - WRITE_NO_RESP | WRITE
    0xFA03 - NOTIFY
    Descriptor on FA02: "TR2512R002-03" (model/version)

  Service 0xAE00 (UNKNOWN - possibly OTA/debug):
    0xAE01 - WRITE_NO_RESP
    0xAE02 - NOTIFY

This script subscribes to both notification characteristics and sends
probe commands to both write characteristics to see what responses we get.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEVICE_NAME_PREFIX = "IDM-"
DEVICE_ADDRESS = "9597D141-2068-32FB-6626-134B9AFEEC98"

KNOWN_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
KNOWN_NOTIFY = "0000fa03-0000-1000-8000-00805f9b34fb"
UNKNOWN_WRITE = "0000ae01-0000-1000-8000-00805f9b34fb"
UNKNOWN_NOTIFY = "0000ae02-0000-1000-8000-00805f9b34fb"


def hex_dump(data: bytes, prefix: str = "  ") -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}: {hex_part:<48s} {ascii_part}")
    return "\n".join(lines)


notifications_log: list[tuple[str, bytes, float]] = []


def make_handler(label: str):
    def handler(_sender: int, data: bytearray) -> None:
        ts = asyncio.get_event_loop().time()
        bdata = bytes(data)
        notifications_log.append((label, bdata, ts))
        logger.info("NOTIFY [%s]: %s", label, bdata.hex())
        if len(bdata) > 16:
            print(hex_dump(bdata))
    return handler


async def send_and_wait(
    client: BleakClient,
    write_uuid: str,
    data: bytes,
    label: str,
    wait: float = 1.5,
) -> list[tuple[str, bytes]]:
    """Send a command and collect any notifications that arrive."""
    before = len(notifications_log)
    logger.info("SEND [%s]: %s -> %s", label, write_uuid[-4:], data.hex())
    try:
        await client.write_gatt_char(write_uuid, data, response=False)
    except Exception as exc:
        logger.info("  Write failed: %s", exc)
        return []
    await asyncio.sleep(wait)
    new = notifications_log[before:]
    if not new:
        logger.info("  (no response)")
    return [(n[0], n[1]) for n in new]


async def main() -> None:
    address = None
    if len(sys.argv) > 1:
        address = sys.argv[1]
    else:
        logger.info("Scanning for iDotMatrix devices...")
        devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
        for _key, (device, adv) in devices.items():
            if (
                isinstance(adv, AdvertisementData)
                and adv.local_name
                and adv.local_name.startswith(DEVICE_NAME_PREFIX)
            ):
                address = device.address
                logger.info("  Found: %s (%s)", adv.local_name, address)
                break

    if not address:
        logger.error("No device found")
        sys.exit(1)

    logger.info("Connecting to %s...", address)
    async with BleakClient(address, timeout=15.0) as client:
        logger.info("Connected! MTU: %d", client.mtu_size)

        await client.start_notify(KNOWN_NOTIFY, make_handler("FA03"))
        logger.info("Subscribed to FA03 (known notify)")

        try:
            await client.start_notify(UNKNOWN_NOTIFY, make_handler("AE02"))
            logger.info("Subscribed to AE02 (unknown notify)")
        except Exception as exc:
            logger.info("Could not subscribe to AE02: %s", exc)

        logger.info("\n=== Phase 1: Probe known service (0xFA) ===")

        probes_fa = [
            ("power-on query", bytes([0x05, 0x00, 0x07, 0x01, 0x01])),
            ("screen brightness", bytes([0x05, 0x00, 0x07, 0x05, 0x00])),
            ("device info?", bytes([0x05, 0x00, 0x04, 0x01, 0x00])),
            ("version?", bytes([0x05, 0x00, 0x08, 0x01, 0x00])),
            ("storage info?", bytes([0x05, 0x00, 0x09, 0x01, 0x00])),
            ("read flash?", bytes([0x05, 0x00, 0x0a, 0x01, 0x00])),
            ("gif count?", bytes([0x05, 0x00, 0x0b, 0x01, 0x00])),
            ("gif list?", bytes([0x05, 0x00, 0x0c, 0x01, 0x00])),
            ("download cmd?", bytes([0x05, 0x00, 0x0d, 0x01, 0x00])),
            ("factory info?", bytes([0x05, 0x00, 0x0e, 0x01, 0x00])),
            ("debug mode?", bytes([0x05, 0x00, 0x0f, 0x01, 0x00])),
            ("flash dump?", bytes([0x05, 0x00, 0x10, 0x01, 0x00])),
        ]

        for label, cmd in probes_fa:
            await send_and_wait(client, KNOWN_WRITE, cmd, label)

        logger.info("\n=== Phase 2: Probe unknown service (0xAE) ===")

        probes_ae = [
            ("AE: hello", bytes([0x00])),
            ("AE: query 01", bytes([0x01])),
            ("AE: query 02", bytes([0x02])),
            ("AE: 5-byte probe", bytes([0x05, 0x00, 0x01, 0x00, 0x00])),
            ("AE: read flash?", bytes([0x05, 0x00, 0x0a, 0x01, 0x00])),
            ("AE: OTA version?", bytes([0x01, 0x00, 0x00, 0x00])),
            ("AE: OTA start?", bytes([0x01, 0x01, 0x00, 0x00])),
            ("AE: flash read 0x0000", struct.pack("<BBI", 0x03, 0x01, 0x00000000)),
            ("AE: flash read header", struct.pack("<BBIH", 0x03, 0x01, 0x00000000, 0x1000)),
        ]

        for label, cmd in probes_ae:
            await send_and_wait(client, UNKNOWN_WRITE, cmd, label)

        logger.info("\n=== Phase 3: Comprehensive opcode scan (0xFA service) ===")
        logger.info("Scanning command bytes 0x00-0x1F on pattern 05 00 XX 01 00...")

        for opcode in range(0x00, 0x20):
            cmd = bytes([0x05, 0x00, opcode, 0x01, 0x00])
            await send_and_wait(client, KNOWN_WRITE, cmd, f"opcode 0x{opcode:02x}", wait=0.5)

        try:
            await client.stop_notify(KNOWN_NOTIFY)
        except Exception:
            pass
        try:
            await client.stop_notify(UNKNOWN_NOTIFY)
        except Exception:
            pass

    logger.info("\n=== Summary ===")
    logger.info("Total notifications received: %d", len(notifications_log))
    for label, data, _ts in notifications_log:
        logger.info("  [%s] %s", label, data.hex())

    logger.info("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
