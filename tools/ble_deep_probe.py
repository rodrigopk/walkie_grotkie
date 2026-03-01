"""Deep probe of iDotMatrix using Telink OTA protocol and FA service opcodes.

Key discovery: the 0xAE00 service is a Telink BLE OTA service.
Telink OTA commands are 16-bit little-endian values.

Also probes FA service opcodes that responded (0x02, 0x04, 0x06, 0x07, 0x0a)
with varied payloads to understand their function.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import sys

from bleak import BleakClient, BleakScanner
from bleak.backends.scanner import AdvertisementData

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DEVICE_NAME_PREFIX = "IDM-"
KNOWN_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
KNOWN_NOTIFY = "0000fa03-0000-1000-8000-00805f9b34fb"
AE_WRITE = "0000ae01-0000-1000-8000-00805f9b34fb"
AE_NOTIFY = "0000ae02-0000-1000-8000-00805f9b34fb"

notifications: list[tuple[str, bytes]] = []


def hex_dump(data: bytes, prefix: str = "    ") -> str:
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}: {hex_part:<48s} {ascii_part}")
    return "\n".join(lines)


def make_handler(label: str):
    def handler(_sender: int, data: bytearray) -> None:
        bdata = bytes(data)
        notifications.append((label, bdata))
        logger.info("  << [%s] %s", label, bdata.hex())
        if len(bdata) > 8:
            print(hex_dump(bdata))
    return handler


async def send(client, uuid, data, label, wait=1.5):
    before = len(notifications)
    logger.info(">> [%s] %s", label, data.hex())
    try:
        await client.write_gatt_char(uuid, data, response=False)
    except Exception as exc:
        logger.info("   Write failed: %s", exc)
        return []
    await asyncio.sleep(wait)
    new_notifs = notifications[before:]
    if not new_notifs:
        logger.info("   (no response)")
    return new_notifs


async def main() -> None:
    logger.info("Scanning for iDotMatrix...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    address = None
    for _key, (device, adv) in devices.items():
        if isinstance(adv, AdvertisementData) and adv.local_name and adv.local_name.startswith(DEVICE_NAME_PREFIX):
            address = device.address
            logger.info("  Found: %s (%s)", adv.local_name, address)
            break

    if not address:
        logger.error("No device found")
        sys.exit(1)

    logger.info("Connecting...")
    async with BleakClient(address, timeout=15.0) as client:
        logger.info("Connected! MTU: %d", client.mtu_size)

        await client.start_notify(KNOWN_NOTIFY, make_handler("FA03"))
        await client.start_notify(AE_NOTIFY, make_handler("AE02"))

        # === Telink OTA Commands (16-bit LE on AE service) ===
        logger.info("\n" + "=" * 60)
        logger.info("TELINK OTA PROTOCOL PROBE (0xAE service)")
        logger.info("=" * 60)

        telink_cmds = [
            ("OTA_VERSION (0xFF00)", struct.pack("<H", 0xFF00)),
            ("OTA_FW_VERSION_REQ (0xFF04)", struct.pack("<HHB", 0xFF04, 0x0000, 0x00)),
            ("OTA_FW_VERSION_REQ v2", struct.pack("<HH", 0xFF04, 0x0000)),
        ]

        for label, cmd in telink_cmds:
            await send(client, AE_WRITE, cmd, label)

        # === Deeper FA opcode exploration ===
        logger.info("\n" + "=" * 60)
        logger.info("FA SERVICE - DEEP OPCODE EXPLORATION")
        logger.info("=" * 60)

        logger.info("\n--- Opcode 0x02 (responded to 05 00 02 01 00) ---")
        for payload in [
            bytes([0x05, 0x00, 0x02, 0x00, 0x00]),
            bytes([0x05, 0x00, 0x02, 0x01, 0x01]),
            bytes([0x05, 0x00, 0x02, 0x02, 0x00]),
            bytes([0x06, 0x00, 0x02, 0x01, 0x00, 0x00]),
        ]:
            await send(client, KNOWN_WRITE, payload, f"0x02 variant", wait=0.8)

        logger.info("\n--- Opcode 0x04 variants ---")
        for payload in [
            bytes([0x05, 0x00, 0x04, 0x00, 0x00]),
            bytes([0x05, 0x00, 0x04, 0x01, 0x01]),
            bytes([0x05, 0x00, 0x04, 0x02, 0x00]),
            bytes([0x05, 0x00, 0x04, 0x03, 0x00]),
        ]:
            await send(client, KNOWN_WRITE, payload, f"0x04 variant", wait=0.8)

        logger.info("\n--- Opcode 0x06 variants ---")
        for payload in [
            bytes([0x05, 0x00, 0x06, 0x00, 0x00]),
            bytes([0x05, 0x00, 0x06, 0x01, 0x01]),
            bytes([0x05, 0x00, 0x06, 0x02, 0x00]),
        ]:
            await send(client, KNOWN_WRITE, payload, f"0x06 variant", wait=0.8)

        logger.info("\n--- Opcode 0x0A deep dive (ACKed - might be image/flash related) ---")
        for payload in [
            bytes([0x05, 0x00, 0x0a, 0x00, 0x00]),
            bytes([0x05, 0x00, 0x0a, 0x01, 0x01]),
            bytes([0x05, 0x00, 0x0a, 0x01, 0x02]),
            bytes([0x05, 0x00, 0x0a, 0x02, 0x00]),
            bytes([0x05, 0x00, 0x0a, 0x02, 0x01]),
            bytes([0x05, 0x00, 0x0a, 0x03, 0x00]),
            bytes([0x06, 0x00, 0x0a, 0x01, 0x00, 0x00]),
            bytes([0x06, 0x00, 0x0a, 0x01, 0x00, 0x01]),
            bytes([0x08, 0x00, 0x0a, 0x01, 0x00, 0x00, 0x00, 0x00]),
        ]:
            await send(client, KNOWN_WRITE, payload, f"0x0A variant", wait=0.8)

        # === Scan higher opcodes (0x20-0xFF) in FA service ===
        logger.info("\n" + "=" * 60)
        logger.info("FA SERVICE - EXTENDED OPCODE SCAN (0x20-0xFF)")
        logger.info("Scanning for any responding opcodes...")
        logger.info("=" * 60)

        responding_opcodes = []
        for opcode in range(0x20, 0x100):
            cmd = bytes([0x05, 0x00, opcode & 0xFF, 0x01, 0x00])
            before = len(notifications)
            try:
                await client.write_gatt_char(KNOWN_WRITE, cmd, response=False)
            except Exception:
                continue
            await asyncio.sleep(0.3)
            if len(notifications) > before:
                responding_opcodes.append(opcode)
                resp = notifications[-1]
                logger.info("  OPCODE 0x%02X RESPONDED: %s", opcode, resp[1].hex())

        if responding_opcodes:
            logger.info("\nResponding opcodes (0x20-0xFF): %s",
                       ", ".join(f"0x{o:02x}" for o in responding_opcodes))
        else:
            logger.info("\nNo additional responding opcodes found in 0x20-0xFF range.")

        try:
            await client.stop_notify(KNOWN_NOTIFY)
            await client.stop_notify(AE_NOTIFY)
        except Exception:
            pass

    logger.info("\n" + "=" * 60)
    logger.info("FULL NOTIFICATION LOG (%d total)", len(notifications))
    logger.info("=" * 60)
    for label, data in notifications:
        logger.info("  [%s] %s", label, data.hex())

    logger.info("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
