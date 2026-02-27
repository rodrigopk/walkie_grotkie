from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from idotmatrix_upload.ble import (
    BLEConnectionError,
    BLEWriteError,
    DEVICE_NAME_PREFIX,
    NOTIFY_UUID,
    WRITE_UUID,
    DeviceConnection,
    connect,
    scan,
)


def _make_mock_client(
    address: str = "AA:BB:CC:DD:EE:FF",
    mtu: int = 512,
    is_connected: bool = True,
) -> MagicMock:
    client = MagicMock()
    client.address = address
    client.mtu_size = mtu
    client.is_connected = is_connected
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.write_gatt_char = AsyncMock()
    client.start_notify = AsyncMock()
    return client


def _make_adv(name: str | None) -> tuple[MagicMock, AdvertisementData]:
    device = MagicMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    adv = AdvertisementData(
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        tx_power=None,
        rssi=-50,
        platform_data=(),
    )
    return device, adv


class TestDeviceConnection:
    @pytest.mark.asyncio
    async def test_write_sub_chunks(self):
        client = _make_mock_client(mtu=23)
        conn = DeviceConnection(client, mtu_size=23)
        data = bytes(60)

        await conn.write(data)

        chunk_size = 20
        expected_calls = (len(data) + chunk_size - 1) // chunk_size
        assert client.write_gatt_char.call_count == expected_calls

        for call in client.write_gatt_char.call_args_list:
            args, kwargs = call
            assert args[0] == WRITE_UUID
            assert len(args[1]) <= chunk_size
            assert kwargs.get("response") is False

    @pytest.mark.asyncio
    async def test_write_large_mtu(self):
        client = _make_mock_client(mtu=512)
        conn = DeviceConnection(client, mtu_size=512)
        data = bytes(1000)

        await conn.write(data)

        chunk_size = 509
        expected_calls = (len(data) + chunk_size - 1) // chunk_size
        assert client.write_gatt_char.call_count == expected_calls

    @pytest.mark.asyncio
    async def test_write_error_raises(self):
        client = _make_mock_client()
        client.write_gatt_char = AsyncMock(side_effect=BleakError("write failed"))
        conn = DeviceConnection(client, mtu_size=512)

        with pytest.raises(BLEWriteError, match="Failed to write"):
            await conn.write(b"\x00" * 10)

    @pytest.mark.asyncio
    async def test_disconnect(self):
        client = _make_mock_client(is_connected=True)
        conn = DeviceConnection(client, mtu_size=512)

        await conn.disconnect()
        client.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self):
        client = _make_mock_client(is_connected=False)
        conn = DeviceConnection(client, mtu_size=512)

        await conn.disconnect()
        client.disconnect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disconnect_suppresses_errors(self):
        client = _make_mock_client(is_connected=True)
        client.disconnect = AsyncMock(side_effect=BleakError("already gone"))
        conn = DeviceConnection(client, mtu_size=512)

        await conn.disconnect()  # should not raise


class TestScan:
    @pytest.mark.asyncio
    async def test_filters_by_prefix(self):
        dev1, adv1 = _make_adv("IDM-1234")
        dev2, adv2 = _make_adv("OtherDevice")
        dev3, adv3 = _make_adv("IDM-5678")

        discover_result = {
            "key1": (dev1, adv1),
            "key2": (dev2, adv2),
            "key3": (dev3, adv3),
        }

        with patch(
            "idotmatrix_upload.ble.BleakScanner.discover",
            new_callable=AsyncMock,
            return_value=discover_result,
        ):
            results = await scan()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_no_devices_returns_empty(self):
        with patch(
            "idotmatrix_upload.ble.BleakScanner.discover",
            new_callable=AsyncMock,
            return_value={},
        ):
            results = await scan()

        assert results == []

    @pytest.mark.asyncio
    async def test_scan_error_raises(self):
        with patch(
            "idotmatrix_upload.ble.BleakScanner.discover",
            new_callable=AsyncMock,
            side_effect=BleakError("Bluetooth off"),
        ):
            with pytest.raises(BLEConnectionError, match="BLE scan failed"):
                await scan()

    @pytest.mark.asyncio
    async def test_custom_prefix(self):
        dev, adv = _make_adv("CUSTOM-42")
        discover_result = {"k": (dev, adv)}

        with patch(
            "idotmatrix_upload.ble.BleakScanner.discover",
            new_callable=AsyncMock,
            return_value=discover_result,
        ):
            results = await scan(name_prefix="CUSTOM-")

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_none_name_skipped(self):
        dev, adv = _make_adv(None)
        discover_result = {"k": (dev, adv)}

        with patch(
            "idotmatrix_upload.ble.BleakScanner.discover",
            new_callable=AsyncMock,
            return_value=discover_result,
        ):
            results = await scan()

        assert results == []


class TestConnect:
    @pytest.mark.asyncio
    async def test_successful_connect(self):
        mock_client = _make_mock_client()

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            conn = await connect("AA:BB:CC:DD:EE:FF")

        assert conn.address == "AA:BB:CC:DD:EE:FF"
        assert conn.mtu_size == 512
        mock_client.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_subscribes_to_notifications(self):
        mock_client = _make_mock_client()
        callback = MagicMock()

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            await connect("AA:BB:CC:DD:EE:FF", on_notification=callback)

        mock_client.start_notify.assert_awaited_once()
        call_args = mock_client.start_notify.call_args
        assert call_args[0][0] == NOTIFY_UUID

    @pytest.mark.asyncio
    async def test_connect_without_notification(self):
        mock_client = _make_mock_client()

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            conn = await connect("AA:BB:CC:DD:EE:FF")

        mock_client.start_notify.assert_not_awaited()
        assert conn is not None

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self):
        mock_client = _make_mock_client()
        mock_client.connect = AsyncMock(side_effect=BleakError("refused"))

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            with pytest.raises(BLEConnectionError, match="Could not connect"):
                await connect("AA:BB:CC:DD:EE:FF")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        mock_client = _make_mock_client()
        mock_client.connect = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            with pytest.raises(BLEConnectionError, match="Could not connect"):
                await connect("AA:BB:CC:DD:EE:FF")

    @pytest.mark.asyncio
    async def test_notification_subscribe_failure_disconnects(self):
        mock_client = _make_mock_client()
        mock_client.start_notify = AsyncMock(side_effect=BleakError("no char"))

        with patch(
            "idotmatrix_upload.ble.BleakClient",
            return_value=mock_client,
        ):
            with pytest.raises(BLEConnectionError, match="notifications"):
                await connect("AA:BB:CC:DD:EE:FF", on_notification=MagicMock())

        mock_client.disconnect.assert_awaited_once()
