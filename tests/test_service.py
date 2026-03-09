from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walkie_grotkie.ble import BLEConnectionError
from walkie_grotkie.protocol import ACK_COMPLETE, ACK_OK
from walkie_grotkie.service import DeviceService, UploadError


def _make_mock_connection(address: str = "AA:BB:CC:DD:EE:FF") -> MagicMock:
    conn = MagicMock()
    conn.address = address
    conn.mtu_size = 512
    conn.write = AsyncMock()
    conn.disconnect = AsyncMock()
    return conn


def _auto_ack_connect(ack_sequence: list[bytes] | None = None):
    """Return a mock ``ble.connect`` that fires ACKs on every write."""
    ack_iter = iter(ack_sequence) if ack_sequence else None

    async def mock_connect(address, on_notification=None, **kwargs):
        conn = _make_mock_connection(address)

        async def mock_write(data):
            if on_notification is not None:
                if ack_iter is not None:
                    try:
                        ack = next(ack_iter)
                    except StopIteration:
                        ack = ACK_OK
                else:
                    ack = ACK_OK
                on_notification(ack)

        conn.write = AsyncMock(side_effect=mock_write)
        return conn

    return mock_connect


@pytest.fixture
def _mock_cache():
    with (
        patch("walkie_grotkie.service.add_to_cache"),
        patch("walkie_grotkie.service.load_cache", return_value=[]),
    ):
        yield


# ---------------------------------------------------------------------------
# Connection / lifecycle
# ---------------------------------------------------------------------------


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_explicit_address(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
            await svc.connect()

            assert svc.is_connected
            assert svc.address == "AA:BB:CC:DD:EE:FF"

            await svc.disconnect()

    @pytest.mark.asyncio
    async def test_connect_via_cache(self, _mock_cache):
        cached_addr = "CC:CC:CC:CC:CC:CC"
        probe_conn = _make_mock_connection(cached_addr)

        async def mock_connect(address, on_notification=None, **kwargs):
            if on_notification is None:
                return probe_conn
            conn = _make_mock_connection(address)
            return conn

        with (
            patch(
                "walkie_grotkie.service.load_cache",
                return_value=[cached_addr],
            ),
            patch(
                "walkie_grotkie.service.ble.connect",
                side_effect=mock_connect,
            ),
            patch("walkie_grotkie.service.add_to_cache"),
            patch(
                "walkie_grotkie.service.ble.scan",
                new_callable=AsyncMock,
            ) as mock_scan,
        ):
            svc = DeviceService(device_address=None, use_cache=True)
            await svc.connect()

            assert svc.is_connected
            mock_scan.assert_not_awaited()
            await svc.disconnect()

    @pytest.mark.asyncio
    async def test_cache_miss_falls_back_to_scan(self, _mock_cache):
        async def mock_connect(address, on_notification=None, **kwargs):
            if on_notification is None:
                raise BLEConnectionError("unreachable")
            conn = _make_mock_connection(address)
            return conn

        with (
            patch(
                "walkie_grotkie.service.load_cache",
                return_value=["BAD:AD:DR:ES:S0:00"],
            ),
            patch(
                "walkie_grotkie.service.ble.connect",
                side_effect=mock_connect,
            ),
            patch(
                "walkie_grotkie.service.ble.scan",
                new_callable=AsyncMock,
                return_value=["AA:BB:CC:DD:EE:FF"],
            ) as mock_scan,
            patch("walkie_grotkie.service.add_to_cache"),
        ):
            svc = DeviceService(device_address=None, use_cache=True)
            await svc.connect()

            assert svc.is_connected
            mock_scan.assert_awaited_once()
            await svc.disconnect()

    @pytest.mark.asyncio
    async def test_scan_no_device_raises(self):
        with (
            patch(
                "walkie_grotkie.service.load_cache",
                return_value=[],
            ),
            patch(
                "walkie_grotkie.service.ble.scan",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            svc = DeviceService(device_address=None)
            with pytest.raises(BLEConnectionError, match="No iDotMatrix device found"):
                await svc.connect()

    @pytest.mark.asyncio
    async def test_connect_updates_cache(self):
        with (
            patch(
                "walkie_grotkie.service.ble.connect",
                side_effect=_auto_ack_connect(),
            ),
            patch(
                "walkie_grotkie.service.load_cache",
                return_value=[],
            ),
            patch("walkie_grotkie.service.add_to_cache") as mock_add,
        ):
            svc = DeviceService(
                device_address="AA:BB:CC:DD:EE:FF", use_cache=True
            )
            await svc.connect()
            mock_add.assert_called_once_with("AA:BB:CC:DD:EE:FF")
            await svc.disconnect()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ) as mock_connect:
            svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
            await svc.connect()
            await svc.connect()
            assert mock_connect.call_count == 1
            await svc.disconnect()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    @pytest.mark.asyncio
    async def test_enter_exit(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                assert svc.is_connected

            assert not svc.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_on_exception(self, _mock_cache):
        mock_conn = _make_mock_connection()

        async def mock_connect(address, on_notification=None, **kwargs):
            return mock_conn

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=mock_connect,
        ):
            with pytest.raises(RuntimeError, match="boom"):
                async with DeviceService(
                    device_address="AA:BB:CC:DD:EE:FF"
                ):
                    raise RuntimeError("boom")

        mock_conn.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
        await svc.disconnect()
        assert not svc.is_connected

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self, _mock_cache):
        mock_conn = _make_mock_connection()

        async def mock_connect(address, on_notification=None, **kwargs):
            return mock_conn

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=mock_connect,
        ):
            svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
            await svc.connect()
            await svc.disconnect()
            await svc.disconnect()

        mock_conn.disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    @pytest.mark.asyncio
    async def test_address_before_connect(self):
        svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
        assert svc.address == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_address_none_before_connect(self):
        svc = DeviceService(device_address=None)
        assert svc.address is None

    @pytest.mark.asyncio
    async def test_is_connected_false_initially(self):
        svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
        assert not svc.is_connected


# ---------------------------------------------------------------------------
# send_packet
# ---------------------------------------------------------------------------


class TestSendPacket:
    @pytest.mark.asyncio
    async def test_send_packet_ack_ok(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                result = await svc.send_packet(b"\x00" * 20)
                assert result == "ok"

    @pytest.mark.asyncio
    async def test_send_packet_ack_complete(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect([ACK_COMPLETE]),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                result = await svc.send_packet(b"\x00" * 20)
                assert result == "complete"

    @pytest.mark.asyncio
    async def test_send_packet_retries_on_timeout(self, _mock_cache):
        call_count = 0

        async def mock_connect(address, on_notification=None, **kwargs):
            conn = _make_mock_connection(address)

            async def mock_write(data):
                nonlocal call_count
                call_count += 1
                if call_count >= 2 and on_notification is not None:
                    on_notification(ACK_OK)

            conn.write = AsyncMock(side_effect=mock_write)
            return conn

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=mock_connect,
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF",
                ack_timeout=0.05,
            ) as svc:
                result = await svc.send_packet(b"\x00" * 20)
                assert result == "ok"

        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_send_packet_retry_exhaustion(self, _mock_cache):
        async def mock_connect(address, on_notification=None, **kwargs):
            conn = _make_mock_connection(address)
            conn.write = AsyncMock()
            return conn

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=mock_connect,
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF",
                ack_timeout=0.05,
                max_retries=2,
            ) as svc:
                with pytest.raises(UploadError, match="failed after"):
                    await svc.send_packet(b"\x00" * 20)

    @pytest.mark.asyncio
    async def test_send_packet_raises_when_disconnected(self):
        svc = DeviceService(device_address="AA:BB:CC:DD:EE:FF")
        with pytest.raises(RuntimeError, match="not connected"):
            await svc.send_packet(b"\x00" * 20)


# ---------------------------------------------------------------------------
# send_packets
# ---------------------------------------------------------------------------


class TestSendPackets:
    @pytest.mark.asyncio
    async def test_send_multiple_packets(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                packets = [b"\x00" * 20, b"\x01" * 20, b"\x02" * 20]
                await svc.send_packets(packets)

    @pytest.mark.asyncio
    async def test_send_packets_progress_callback(self, _mock_cache):
        progress: list[tuple[int, int]] = []

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                packets = [b"\x00" * 20, b"\x01" * 20]
                await svc.send_packets(
                    packets, on_progress=lambda idx, total: progress.append((idx, total))
                )

        assert progress == [(0, 2), (1, 2)]

    @pytest.mark.asyncio
    async def test_send_packets_stops_on_complete(self, _mock_cache):
        """Device's COMPLETE ACK must stop further sends; the second packet is dropped."""
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect([ACK_COMPLETE, ACK_OK]),
        ) as mock_connect:
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                conn = svc._connection
                packets = [b"\x00" * 20, b"\x01" * 20]
                await svc.send_packets(packets)

            # Only the first packet should have been written; the second must
            # never be sent because the device already signaled completion.
            assert conn.write.await_count == 1

    @pytest.mark.asyncio
    async def test_send_packets_progress_includes_completing_packet(self, _mock_cache):
        """Progress callback must still fire for the packet that triggers COMPLETE."""
        progress: list[tuple[int, int]] = []

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect([ACK_COMPLETE, ACK_OK]),
        ):
            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                packets = [b"\x00" * 20, b"\x01" * 20]
                await svc.send_packets(
                    packets, on_progress=lambda idx, total: progress.append((idx, total))
                )

        # Progress must be reported for the single packet that was actually sent.
        assert progress == [(0, 2)]


# ---------------------------------------------------------------------------
# upload_gif
# ---------------------------------------------------------------------------


class TestUploadGif:
    @pytest.mark.asyncio
    async def test_upload_gif_builds_and_sends_packets(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            gif_data = b"GIF89a" + b"\x00" * 200

            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                await svc.upload_gif(gif_data)

    @pytest.mark.asyncio
    async def test_upload_gif_progress(self, _mock_cache):
        progress: list[tuple[int, int]] = []

        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            gif_data = b"GIF89a" + b"\x00" * 200

            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                await svc.upload_gif(
                    gif_data,
                    on_progress=lambda idx, total: progress.append((idx, total)),
                )

        assert len(progress) >= 1

    @pytest.mark.asyncio
    async def test_upload_gif_with_completion(self, _mock_cache):
        with patch(
            "walkie_grotkie.service.ble.connect",
            side_effect=_auto_ack_connect([ACK_COMPLETE]),
        ):
            gif_data = b"GIF89a" + b"\x00" * 200

            async with DeviceService(
                device_address="AA:BB:CC:DD:EE:FF"
            ) as svc:
                await svc.upload_gif(gif_data)
