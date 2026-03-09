from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from walkie_grotkie.generate import generate_spinning_number_gif
from walkie_grotkie.preprocess import ValidationError
from walkie_grotkie.upload import upload_gifs


def _make_mock_service():
    """Build a mock DeviceService that records upload_gif calls."""
    svc = AsyncMock()
    svc.upload_gif = AsyncMock()
    svc.connect = AsyncMock()
    svc.disconnect = AsyncMock()
    svc.is_connected = True
    svc.address = "AA:BB:CC:DD:EE:FF"
    return svc


def _patch_device_service(mock_svc=None):
    """Return a context manager that patches DeviceService in upload module.

    The patched class returns *mock_svc* (or a fresh mock) from ``__aenter__``.
    """
    if mock_svc is None:
        mock_svc = _make_mock_service()

    mock_cls = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_svc)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_cls.return_value = mock_ctx

    return patch("walkie_grotkie.upload.DeviceService", mock_cls), mock_svc, mock_cls


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
        patcher, mock_svc, _ = _patch_device_service()
        with patcher:
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

        mock_svc.upload_gif.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multi_gif_upload(self, two_gifs: list[Path]):
        patcher, mock_svc, _ = _patch_device_service()
        with patcher:
            await upload_gifs(
                two_gifs,
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

        assert mock_svc.upload_gif.await_count == 2

    @pytest.mark.asyncio
    async def test_progress_callback(self, single_gif: Path):
        progress_calls: list[tuple] = []

        def on_progress(file_idx, total_files, chunk_idx, total_chunks):
            progress_calls.append((file_idx, total_files, chunk_idx, total_chunks))

        mock_svc = _make_mock_service()

        async def fake_upload_gif(gif_data, chunk_size=4096, on_progress=None):
            if on_progress is not None:
                on_progress(0, 1)

        mock_svc.upload_gif = AsyncMock(side_effect=fake_upload_gif)

        patcher, _, _ = _patch_device_service(mock_svc)
        with patcher:
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
                on_progress=on_progress,
            )

        assert len(progress_calls) >= 1
        file_idx, total_files, chunk_idx, total_chunks = progress_calls[0]
        assert file_idx == 0
        assert total_files == 1

    @pytest.mark.asyncio
    async def test_with_preprocessing(self, single_gif: Path, tmp_path: Path):
        processed_dir = tmp_path / "processed"

        patcher, mock_svc, _ = _patch_device_service()
        with patcher:
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=True,
                preprocessed_dir=processed_dir,
            )

        assert processed_dir.exists()
        processed_files = list(processed_dir.iterdir())
        assert len(processed_files) == 1
        mock_svc.upload_gif.assert_awaited_once()

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
    async def test_empty_paths_noop(self):
        await upload_gifs([], device_address="AA:BB:CC:DD:EE:FF")

    @pytest.mark.asyncio
    async def test_upload_delay_sleeps_between_files(self, two_gifs: list[Path]):
        patcher, _, _ = _patch_device_service()
        with patcher, patch(
            "walkie_grotkie.upload.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await upload_gifs(
                two_gifs,
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
                upload_delay=0.1,
            )

        mock_sleep.assert_awaited_once_with(0.1)

    @pytest.mark.asyncio
    async def test_upload_delay_not_applied_for_single_file(self, single_gif: Path):
        patcher, _, _ = _patch_device_service()
        with patcher, patch(
            "walkie_grotkie.upload.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await upload_gifs(
                [single_gif],
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
                upload_delay=0.1,
            )

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_upload_no_delay_by_default(self, two_gifs: list[Path]):
        patcher, _, _ = _patch_device_service()
        with patcher, patch(
            "walkie_grotkie.upload.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await upload_gifs(
                two_gifs,
                device_address="AA:BB:CC:DD:EE:FF",
                preprocess=False,
            )

        mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_device_service_receives_params(self, single_gif: Path):
        """Verify that upload_gifs forwards the right params to DeviceService."""
        patcher, _, mock_cls = _patch_device_service()
        with patcher:
            await upload_gifs(
                [single_gif],
                device_address="DD:DD:DD:DD:DD:DD",
                device_name_prefix="TEST-",
                ack_timeout=1.5,
                max_retries=5,
                use_cache=False,
                preprocess=False,
            )

        mock_cls.assert_called_once_with(
            device_address="DD:DD:DD:DD:DD:DD",
            device_name_prefix="TEST-",
            ack_timeout=1.5,
            max_retries=5,
            use_cache=False,
        )
