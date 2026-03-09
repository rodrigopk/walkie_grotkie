"""CLI contract tests: exit codes, parameter validation, and command routing.

Uses Click's CliRunner so tests run in-process without BLE hardware.
All async entrypoints (upload_gifs, run_chat, run_voice_chat) are replaced
with synchronous or async no-op stubs so only the CLI layer is exercised.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from walkie_grotkie.cli import main, _parse_size


# ---------------------------------------------------------------------------
# _parse_size (unit-level, no subprocess needed)
# ---------------------------------------------------------------------------


class TestParseSizeHelper:
    def test_valid_size_returns_tuple(self):
        assert _parse_size("64x64") == (64, 64)

    def test_case_insensitive(self):
        assert _parse_size("32X32") == (32, 32)

    def test_asymmetric_size(self):
        assert _parse_size("128x64") == (128, 64)

    def test_missing_separator_raises(self):
        import click
        with pytest.raises(click.BadParameter, match="Invalid size"):
            _parse_size("64")

    def test_non_numeric_raises(self):
        import click
        with pytest.raises(click.BadParameter, match="Invalid size"):
            _parse_size("axb")

    def test_extra_separator_raises(self):
        import click
        with pytest.raises(click.BadParameter, match="Invalid size"):
            _parse_size("64x64x64")


# ---------------------------------------------------------------------------
# `upload` command
# ---------------------------------------------------------------------------


def _fake_upload(**_kwargs):
    """Sync wrapper so we can monkeypatch asyncio.run."""
    pass


class TestUploadCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        with patch("walkie_grotkie.upload.upload_gifs", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(main, ["upload", str(gif), "--no-preprocess"])

        assert result.exit_code == 0
        assert "Upload complete" in result.output

    def test_invalid_size_exits_nonzero(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        result = runner.invoke(main, ["upload", str(gif), "--size", "bad"])
        assert result.exit_code != 0
        assert "Invalid size" in result.output

    def test_validation_error_exits_one(self, tmp_path: Path):
        from walkie_grotkie.preprocess import ValidationError

        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        def raise_validation(*args, **kwargs):
            raise ValidationError([(gif, "not a valid GIF")])

        with patch("walkie_grotkie.cli.asyncio.run", side_effect=raise_validation):
            result = runner.invoke(main, ["upload", str(gif)])

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_ble_connection_error_exits_two(self, tmp_path: Path):
        from walkie_grotkie.ble import BLEConnectionError

        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=BLEConnectionError("no device"),
        ):
            result = runner.invoke(main, ["upload", str(gif)])

        assert result.exit_code == 2
        assert "Device error:" in result.output

    def test_upload_error_exits_two(self, tmp_path: Path):
        from walkie_grotkie.upload import UploadError

        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=UploadError("chunk failed"),
        ):
            result = runner.invoke(main, ["upload", str(gif)])

        assert result.exit_code == 2
        assert "Upload error:" in result.output

    def test_forwards_device_addr(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        captured = {}

        def capture_coroutine(coro):
            # Drain the coroutine immediately so we can inspect its args.
            async def _drain():
                try:
                    await coro
                except Exception:
                    pass
            asyncio.run(_drain())

        with patch("walkie_grotkie.upload.upload_gifs", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(
                main,
                ["upload", str(gif), "--device-addr", "AA:BB:CC:DD:EE:FF", "--no-preprocess"],
            )

        assert result.exit_code == 0
        mock_fn.assert_awaited_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["device_address"] == "AA:BB:CC:DD:EE:FF"

    def test_no_preprocess_flag_forwarded(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        with patch("walkie_grotkie.upload.upload_gifs", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(main, ["upload", str(gif), "--no-preprocess"])

        assert result.exit_code == 0
        assert mock_fn.call_args.kwargs["preprocess"] is False

    def test_no_cache_flag_forwarded(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        with patch("walkie_grotkie.upload.upload_gifs", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(main, ["upload", str(gif), "--no-cache", "--no-preprocess"])

        assert result.exit_code == 0
        assert mock_fn.call_args.kwargs["use_cache"] is False


# ---------------------------------------------------------------------------
# `generate` command
# ---------------------------------------------------------------------------


class TestGenerateCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        with patch("walkie_grotkie.generate.generate_spinning_number_gif") as mock_gen:
            fake_path = tmp_path / "number_01.gif"
            fake_path.write_bytes(b"GIF89a")
            mock_gen.return_value = fake_path
            result = runner.invoke(
                main, ["generate", "--output-dir", str(tmp_path), "--count", "1"]
            )

        assert result.exit_code == 0
        assert "Generated" in result.output


# ---------------------------------------------------------------------------
# `preprocess` command
# ---------------------------------------------------------------------------


class TestPreprocessCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        from walkie_grotkie.preprocess import PreprocessResult

        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)
        out_dir = tmp_path / "processed"

        fake_result = PreprocessResult(
            input_path=gif,
            output_path=out_dir / "test.gif",
            original_size=(32, 32),
            output_size=(32, 32),
            original_bytes=100,
            output_bytes=80,
            frame_count=3,
        )

        with patch("walkie_grotkie.preprocess.preprocess_batch", return_value=[fake_result]):
            result = runner.invoke(
                main, ["preprocess", str(gif), "--output-dir", str(out_dir)]
            )

        assert result.exit_code == 0
        assert "Preprocessed" in result.output

    def test_validation_error_exits_one(self, tmp_path: Path):
        from walkie_grotkie.preprocess import ValidationError

        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)
        out_dir = tmp_path / "processed"

        with patch(
            "walkie_grotkie.preprocess.preprocess_batch",
            side_effect=ValidationError([(gif, "bad format")]),
        ):
            result = runner.invoke(
                main, ["preprocess", str(gif), "--output-dir", str(out_dir)]
            )

        assert result.exit_code == 1
        assert "Error:" in result.output

    def test_invalid_size_exits_nonzero(self, tmp_path: Path):
        runner = CliRunner()
        gif = tmp_path / "test.gif"
        gif.write_bytes(b"GIF89a" + b"\x00" * 100)

        result = runner.invoke(main, ["preprocess", str(gif), "--size", "notasize"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# `assemble-gif` command
# ---------------------------------------------------------------------------


class TestAssembleGifCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        from PIL import Image

        runner = CliRunner()
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        for i in range(3):
            img = Image.new("RGBA", (32, 32), (i * 80, 0, 0, 255))
            img.save(frames_dir / f"frame_{i:03d}.png")

        out = tmp_path / "out.gif"

        with patch("walkie_grotkie.generate.assemble_gif_from_frames") as mock_asm:
            mock_asm.return_value = out
            out.write_bytes(b"GIF89a" + b"\x00" * 50)
            result = runner.invoke(
                main, ["assemble-gif", str(frames_dir), "-o", str(out)]
            )

        assert result.exit_code == 0
        assert "Assembled" in result.output

    def test_no_frames_exits_nonzero(self, tmp_path: Path):
        runner = CliRunner()
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        out = tmp_path / "out.gif"

        result = runner.invoke(main, ["assemble-gif", str(empty_dir), "-o", str(out)])
        assert result.exit_code != 0

    def test_invalid_size_exits_nonzero(self, tmp_path: Path):
        from PIL import Image

        runner = CliRunner()
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        Image.new("RGBA", (32, 32), "red").save(frames_dir / "frame_000.png")
        out = tmp_path / "out.gif"

        result = runner.invoke(
            main, ["assemble-gif", str(frames_dir), "-o", str(out), "--size", "bad"]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# `chat` command
# ---------------------------------------------------------------------------


class TestChatCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch("walkie_grotkie.chat.run_chat", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(
                main,
                [
                    "chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 0

    def test_ble_error_exits_two(self, tmp_path: Path):
        from walkie_grotkie.ble import BLEConnectionError

        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=BLEConnectionError("no device"),
        ):
            result = runner.invoke(
                main,
                [
                    "chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 2

    def test_keyboard_interrupt_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=KeyboardInterrupt,
        ):
            result = runner.invoke(
                main,
                [
                    "chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Goodbye" in result.output

    def test_missing_api_key_exits_nonzero(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        result = runner.invoke(
            main,
            ["chat", "--animations-dir", str(anim_dir)],
            env={"ANTHROPIC_API_KEY": ""},
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# `voice-chat` command
# ---------------------------------------------------------------------------


class TestVoiceChatCommand:
    def test_success_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch("walkie_grotkie.voice_chat.run_voice_chat", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            result = runner.invoke(
                main,
                [
                    "voice-chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 0

    def test_ble_error_exits_two(self, tmp_path: Path):
        from walkie_grotkie.ble import BLEConnectionError

        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=BLEConnectionError("no device"),
        ):
            result = runner.invoke(
                main,
                [
                    "voice-chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 2

    def test_keyboard_interrupt_exits_zero(self, tmp_path: Path):
        runner = CliRunner()
        anim_dir = tmp_path / "grot_animations"
        anim_dir.mkdir()

        with patch(
            "walkie_grotkie.cli.asyncio.run",
            side_effect=KeyboardInterrupt,
        ):
            result = runner.invoke(
                main,
                [
                    "voice-chat",
                    "--api-key", "test-key",
                    "--animations-dir", str(anim_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Goodbye" in result.output
