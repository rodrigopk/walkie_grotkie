import struct
import zlib

import pytest

from idotmatrix_upload.protocol import (
    ACK_COMPLETE,
    ACK_OK,
    CHUNK_FLAG_CONTINUATION,
    CHUNK_FLAG_FIRST,
    DEFAULT_CHUNK_SIZE,
    HEADER_SIZE,
    HEADER_TRAILER,
    TYPE_GIF,
    build_chunk_header,
    build_packets,
    parse_ack,
)


class TestBuildChunkHeader:
    def test_header_is_16_bytes(self):
        header = build_chunk_header(100, 100, 0xDEADBEEF, is_first=True)
        assert len(header) == HEADER_SIZE

    def test_first_chunk_flag(self):
        header = build_chunk_header(100, 200, 0, is_first=True)
        assert header[4] == CHUNK_FLAG_FIRST

    def test_continuation_chunk_flag(self):
        header = build_chunk_header(100, 200, 0, is_first=False)
        assert header[4] == CHUNK_FLAG_CONTINUATION

    def test_chunk_length_includes_header(self):
        data_len = 4096
        header = build_chunk_header(data_len, 8000, 0, is_first=True)
        chunk_length = struct.unpack_from("<H", header, 0)[0]
        assert chunk_length == HEADER_SIZE + data_len

    def test_type_marker(self):
        header = build_chunk_header(100, 100, 0, is_first=True, type_marker=TYPE_GIF)
        assert header[2] == TYPE_GIF

    def test_reserved_byte_is_zero(self):
        header = build_chunk_header(100, 100, 0, is_first=True)
        assert header[3] == 0x00

    def test_total_data_size_encoding(self):
        total = 6329
        header = build_chunk_header(100, total, 0, is_first=True)
        encoded = struct.unpack_from("<I", header, 5)[0]
        assert encoded == total

    def test_crc32_encoding(self):
        crc = 0x14CB42DB
        header = build_chunk_header(100, 100, crc, is_first=True)
        encoded = struct.unpack_from("<I", header, 9)[0]
        assert encoded == crc

    def test_trailer_bytes(self):
        header = build_chunk_header(100, 100, 0, is_first=True)
        assert header[13:16] == HEADER_TRAILER

    def test_wire_capture_master_header(self):
        """Verify against real captured master header from the reference client.

        Captured first chunk header for a 6329-byte GIF with CRC 0x14CB42DB:
            10 10 01 00 00 b9 18 00 00 db 42 cb 14 05 00 0d

        chunk_length = 0x1010 = 4112 = 16 + 4096
        total_data_size = 0x000018b9 = 6329
        crc32 = 0x14cb42db
        """
        header = build_chunk_header(
            chunk_data_len=4096,
            total_data_size=6329,
            crc32=0x14CB42DB,
            is_first=True,
        )
        expected = bytes.fromhex("10100100 00b91800 00db42cb 1405000d".replace(" ", ""))
        assert header == expected

    def test_wire_capture_secondary_header(self):
        """Verify against the captured second chunk header for the same GIF.

        Captured:
            c9 08 01 00 02 b9 18 00 00 db 42 cb 14 05 00 0d

        chunk_length = 0x08c9 = 2249 = 16 + 2233
        """
        header = build_chunk_header(
            chunk_data_len=2233,
            total_data_size=6329,
            crc32=0x14CB42DB,
            is_first=False,
        )
        expected = bytes.fromhex("c90801000 2b91800 00db42cb 1405000d".replace(" ", ""))
        assert header == expected


class TestBuildPackets:
    def test_empty_data_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            build_packets(b"")

    def test_single_chunk_small_data(self):
        data = b"\x00" * 100
        packets = build_packets(data)
        assert len(packets) == 1
        assert len(packets[0]) == HEADER_SIZE + 100

    def test_single_chunk_exact_boundary(self):
        data = b"\x00" * DEFAULT_CHUNK_SIZE
        packets = build_packets(data)
        assert len(packets) == 1

    def test_multi_chunk(self):
        data = b"\x00" * (DEFAULT_CHUNK_SIZE + 1)
        packets = build_packets(data)
        assert len(packets) == 2
        assert packets[0][4] == CHUNK_FLAG_FIRST
        assert packets[1][4] == CHUNK_FLAG_CONTINUATION

    def test_multi_chunk_sizes(self):
        data = b"\x00" * (DEFAULT_CHUNK_SIZE * 2 + 500)
        packets = build_packets(data)
        assert len(packets) == 3

        first_data_len = len(packets[0]) - HEADER_SIZE
        second_data_len = len(packets[1]) - HEADER_SIZE
        third_data_len = len(packets[2]) - HEADER_SIZE

        assert first_data_len == DEFAULT_CHUNK_SIZE
        assert second_data_len == DEFAULT_CHUNK_SIZE
        assert third_data_len == 500

    def test_crc_matches_zlib(self):
        data = b"Hello iDotMatrix!" * 100
        packets = build_packets(data)
        expected_crc = zlib.crc32(data) & 0xFFFFFFFF
        encoded_crc = struct.unpack_from("<I", packets[0], 9)[0]
        assert encoded_crc == expected_crc

    def test_total_data_size_consistent_across_chunks(self):
        data = b"\xAB" * (DEFAULT_CHUNK_SIZE * 3)
        packets = build_packets(data)
        for packet in packets:
            total = struct.unpack_from("<I", packet, 5)[0]
            assert total == len(data)

    def test_crc_consistent_across_chunks(self):
        data = b"\xCD" * (DEFAULT_CHUNK_SIZE * 2 + 1)
        packets = build_packets(data)
        crcs = [struct.unpack_from("<I", p, 9)[0] for p in packets]
        assert len(set(crcs)) == 1

    def test_custom_chunk_size(self):
        data = b"\x00" * 1000
        packets = build_packets(data, chunk_size=300)
        assert len(packets) == 4  # 300 + 300 + 300 + 100

    def test_reassembled_data_matches_original(self):
        data = bytes(range(256)) * 20  # 5120 bytes
        packets = build_packets(data)
        reassembled = b"".join(p[HEADER_SIZE:] for p in packets)
        assert reassembled == data

    def test_chunk_length_field_matches_packet_length(self):
        data = b"\xFF" * 7000
        packets = build_packets(data)
        for packet in packets:
            declared = struct.unpack_from("<H", packet, 0)[0]
            assert declared == len(packet)


class TestParseAck:
    def test_ok(self):
        assert parse_ack(ACK_OK) == "ok"

    def test_complete(self):
        assert parse_ack(ACK_COMPLETE) == "complete"

    def test_unknown(self):
        assert parse_ack(b"\x00\x00\x00") == "unknown"

    def test_empty(self):
        assert parse_ack(b"") == "unknown"

    def test_raw_ok_bytes(self):
        assert parse_ack(bytes([0x05, 0x00, 0x01, 0x00, 0x01])) == "ok"

    def test_raw_complete_bytes(self):
        assert parse_ack(bytes([0x05, 0x00, 0x01, 0x00, 0x03])) == "complete"
