from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idotmatrix_upload.ble import BLEConnectionError
from idotmatrix_upload.generate import generate_spinning_number_gif
from idotmatrix_upload.preprocess import ValidationError
from idotmatrix_upload.protocol import ACK_COMPLETE, ACK_OK
from idotmatrix_upload.upload import UploadError, upload_gifs


def _make_mock_connection():
    conn = MagicMock()
    conn.address = "AA:BB:CC:DD:EE:FF"
    conn.mtu_size = 512
    conn.write = AsyncMock()
    conn.disconnect = AsyncMock()
    return conn


def _auto_ack_connect(ack_sequence: list[bytes] | None = None):
    """Create a mock connect that auto-fires ACK notifications.

    If ack_sequence is None, always sends ACK_OK.
    """
    ack_iter = iter(ack_sequence) if ack_sequence else None

    async def mock_connect(address, on_notification=None, **kwargs):
        conn = _make_mock_connection()
        call_count = 0

        async def mock_write(data):
            nonlocal call_count
            if on_notification is not None:
                if ack_iter is not None:
                    try:
                        ack = next(ack_iter)
                    except StopIteration:
                        ack = ACK_OK
                else:
                    ack = ACK_OK
                on_notification(ack)
            call_count += 1

        conn.write = AsyncMock(side_effect=mock_write)
        return conn

    return mock_connect


@pytest.fixture
def single_gif(tmp_path: Path) -> Path:
    return generate_spinning_number_gif(
        1, tmp_path / "input" / "test.gif", size=32, num_frames=2
    )


@pytest.fixture
def two_gifs(tmp_path: Path) -> list[Path]:
    return [
        generate_spinning_number_gif(
            i, tmp_path / "input" / f"test_{i}.gif", size=32, num_frames=2
        )
        for i in range(1, 3)
    ]


class TestUploadGifs:
    @pytest.mark.asyncio
    async def test_single_gif_upload(self, single_gif: Path):
        with patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

    @pytest.mark.asyncio
    async def test_multi_gif_upload(self, two_gifs: list[Path]):
        with patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            await upload_gifs(
                two_gifs,
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

    @pytest.mark.asyncio
    async def test_progress_callback(self, single_gif: Path):
        progress_calls: list[tuple] = []

        def on_progress(file_idx, total_files, chunk_idx, total_chunks):
            progress_calls.append((file_idx, total_files, chunk_idx, total_chunks))

        with patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
                on_progress=on_progress,
            )

        assert len(progress_calls) >= 1
        for file_idx, total_files, chunk_idx, total_chunks in progress_calls:
            assert file_idx == 0
            assert total_files == 1
            assert 0 <= chunk_idx < total_chunks

    @pytest.mark.asyncio
    async def test_ack_timeout_triggers_retry(self, single_gif: Path):
        call_count = 0

        async def mock_connect(address, on_notification=None, **kwargs):
            conn = _make_mock_connection()

            async def mock_write(data):
                nonlocal call_count
                call_count += 1
                # Succeed only on the second attempt
                if call_count >= 2 and on_notification is not None:
                    on_notification(ACK_OK)

            conn.write = AsyncMock(side_effect=mock_write)
            return conn

        with patch("idotmatrix_upload.upload.ble.connect", side_effect=mock_connect):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
                ack_timeout=0.1,
            )

        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_retry_exhaustion_raises(self, single_gif: Path):
        async def mock_connect(address, on_notification=None, **kwargs):
            conn = _make_mock_connection()
            # Never fire ACK
            conn.write = AsyncMock()
            return conn

        with patch("idotmatrix_upload.upload.ble.connect", side_effect=mock_connect):
            with pytest.raises(UploadError, match="failed after"):
                await upload_gifs(
                    [single_gif],
                    device_address="AA:BB:CC:DD:EE:FF",
                    preprocess=False,
                    ack_timeout=0.05,
                    max_retries=2,
                )

    @pytest.mark.asyncio
    async def test_disconnect_on_failure(self, single_gif: Path):
        mock_conn = _make_mock_connection()
        mock_conn.write = AsyncMock()  # Never ACKs

        async def mock_connect(address, on_notification=None, **kwargs):
            return mock_conn

        with patch("idotmatrix_upload.upload.ble.connect", side_effect=mock_connect):
            with pytest.raises(UploadError):
                await upload_gifs(
                    [single_gif],
                    device_address="AA:BB:CC:DD:EE:FF",
                    preprocess=False,
                    ack_timeout=0.05,
                    max_retries=1,
                )

        mock_conn.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_on_success(self, single_gif: Path):
        last_conn = None

        async def mock_connect(address, on_notification=None, **kwargs):
            nonlocal last_conn
            conn = _make_mock_connection()

            async def mock_write(data):
                if on_notification is not None:
                    on_notification(ACK_OK)

            conn.write = AsyncMock(side_effect=mock_write)
            last_conn = conn
            return conn

        with patch("idotmatrix_upload.upload.ble.connect", side_effect=mock_connect):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

        assert last_conn is not None
        last_conn.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_preprocessing(self, single_gif: Path, tmp_path: Path):
        processed_dir = tmp_path / "processed"

        with patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=True,
                preprocessed_dir=processed_dir,
            )

        assert processed_dir.exists()
        processed_files = list(processed_dir.iterdir())
        assert len(processed_files) == 1

    @pytest.mark.asyncio
    async def test_preprocessing_validation_error(self, tmp_path: Path):
        bad_file = tmp_path / "not_a_gif.txt"
        bad_file.write_text("nope")

        with pytest.raises(ValidationError):
            await upload_gifs(
                [bad_file],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=True,
            )

    @pytest.mark.asyncio
    async def test_scan_when_no_address(self, single_gif: Path):
        with patch(
            "idotmatrix_upload.upload.ble.scan",
            new_callable=AsyncMock,
            return_value=["AA:BB:CC:DD:EE:FF"],
        ), patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect(),
        ):
            await upload_gifs(
                [single_gif],
                device_address=None,
                preprocess=False,
            )

    @pytest.mark.asyncio
    async def test_scan_no_device_found(self, single_gif: Path):
        with patch(
            "idotmatrix_upload.upload.ble.scan",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with pytest.raises(BLEConnectionError, match="No iDotMatrix device found"):
                await upload_gifs(
                    [single_gif],
                    device_address=None,
                    preprocess=False,
                )

    @pytest.mark.asyncio
    async def test_empty_paths_noop(self):
        await upload_gifs([], device_address="AA:BB:CC:DD:EE:FF")

    @pytest.mark.asyncio
    async def test_completion_notification_handled(self, single_gif: Path):
        """Upload should succeed even when device sends 'complete' instead of 'ok'."""
        with patch(
            "idotmatrix_upload.upload.ble.connect",
            side_effect=_auto_ack_connect([ACK_COMPLETE]),
        ):
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )
