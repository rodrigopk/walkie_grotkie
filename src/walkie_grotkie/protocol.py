"""Pure packet construction for the iDotMatrix BLE upload protocol.

This module contains no I/O — it receives bytes and returns bytes.
All multi-byte integers are little-endian.

Protocol reference (verified against wire captures and the reference client
at https://github.com/derkalle4/python3-idotmatrix-library):

Each protocol-level chunk carries a 16-byte header:

    Offset  Size       Field
    0-1     uint16 LE  chunk_length (header + data)
    2       uint8      type_marker  (0x01 = GIF)
    3       uint8      reserved     (0x00)
    4       uint8      chunk_flag   (0x00 first, 0x02 continuation)
    5-8     uint32 LE  total_data_size (raw payload length, no headers)
    9-12    uint32 LE  crc32        (of entire raw payload)
    13-15   bytes      trailer      (0x05 0x00 0x0D, fixed)
"""

import struct
import zlib

HEADER_SIZE: int = 16
DEFAULT_CHUNK_SIZE: int = 4096

TYPE_GIF: int = 0x01
TYPE_TEXT: int = 0x03

CHUNK_FLAG_FIRST: int = 0x00
CHUNK_FLAG_CONTINUATION: int = 0x02

HEADER_TRAILER: bytes = bytes([0x05, 0x00, 0x0D])

ACK_OK: bytes = bytes([0x05, 0x00, 0x01, 0x00, 0x01])
ACK_COMPLETE: bytes = bytes([0x05, 0x00, 0x01, 0x00, 0x03])


def build_chunk_header(
    chunk_data_len: int,
    total_data_size: int,
    crc32: int,
    is_first: bool,
    type_marker: int = TYPE_GIF,
) -> bytes:
    """Build a 16-byte chunk header.

    Args:
        chunk_data_len: Length of the data portion of this chunk (not including header).
        total_data_size: Total length of the raw payload across all chunks.
        crc32: CRC32 of the entire raw payload.
        is_first: True for the first (or only) chunk, False for continuations.
        type_marker: Payload type (default TYPE_GIF = 0x01).

    Returns:
        16-byte header as bytes.
    """
    chunk_length = HEADER_SIZE + chunk_data_len
    flag = CHUNK_FLAG_FIRST if is_first else CHUNK_FLAG_CONTINUATION

    # Pack: uint16 chunk_length, uint8 type, uint8 reserved, uint8 flag,
    #       uint32 total_size, uint32 crc (as signed to handle high-bit CRC values)
    header = struct.pack(
        "<HBBBI",
        chunk_length,
        type_marker,
        0x00,
        flag,
        total_data_size,
    )
    # CRC32 can be negative in Python (signed), pack as unsigned
    header += struct.pack("<I", crc32 & 0xFFFFFFFF)
    header += HEADER_TRAILER

    assert len(header) == HEADER_SIZE
    return header


def build_packets(
    gif_data: bytes,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> list[bytes]:
    """Split raw GIF data into protocol packets, each with a 16-byte header.

    Args:
        gif_data: The raw GIF file bytes.
        chunk_size: Maximum data bytes per chunk (default 4096).

    Returns:
        List of packets (header + data) ready to send over BLE.

    Raises:
        ValueError: If gif_data is empty.
    """
    if not gif_data:
        raise ValueError("GIF data must not be empty")

    total_size = len(gif_data)
    crc = zlib.crc32(gif_data) & 0xFFFFFFFF

    packets: list[bytes] = []
    for i in range(0, total_size, chunk_size):
        chunk = gif_data[i : i + chunk_size]
        is_first = i == 0
        header = build_chunk_header(len(chunk), total_size, crc, is_first)
        packets.append(header + chunk)

    return packets


def parse_ack(notification: bytes) -> str:
    """Decode a device notification into a semantic result.

    Args:
        notification: Raw bytes from the device notification characteristic.

    Returns:
        "ok" if chunk acknowledged, "complete" if upload finished, "unknown" otherwise.
    """
    if notification == ACK_OK:
        return "ok"
    if notification == ACK_COMPLETE:
        return "complete"
    return "unknown"
