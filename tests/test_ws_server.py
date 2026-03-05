"""Tests for the GrotWebSocketServer WebSocket API.

All BLE and AI interactions are mocked so no device or API key is needed.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idotmatrix_upload.ws_server import DEFAULT_PORT, GrotWebSocketServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_server(**kwargs) -> GrotWebSocketServer:
    """Return a server instance with sensible test defaults."""
    defaults = dict(
        api_key="test-key",
        animations_dir=Path("grot_animations"),
    )
    defaults.update(kwargs)
    return GrotWebSocketServer(**defaults)


def _b64_wav() -> str:
    """Return a minimal (8-byte) base64 WAV payload for testing."""
    return base64.b64encode(b"\x00" * 8).decode()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_port(self):
        server = _make_server()
        assert server._port == DEFAULT_PORT

    def test_default_model(self):
        server = _make_server()
        assert server._model == "gpt-4o"

    def test_default_tts_voice(self):
        server = _make_server()
        assert server._tts_voice == "nova"

    def test_custom_port(self):
        server = _make_server(port=9000)
        assert server._port == 9000

    def test_api_key_stored(self):
        server = _make_server(api_key="sk-test")
        assert server._api_key == "sk-test"

    def test_initial_client_is_none(self):
        server = _make_server()
        assert server._client is None

    def test_initial_processing_is_false(self):
        server = _make_server()
        assert server._processing is False


# ---------------------------------------------------------------------------
# _send
# ---------------------------------------------------------------------------


class TestSend:
    @pytest.mark.asyncio
    async def test_send_serializes_json(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        await server._send({"type": "status", "text": "hello"})
        mock_ws.send.assert_called_once_with('{"type": "status", "text": "hello"}')

    @pytest.mark.asyncio
    async def test_send_no_client_is_noop(self):
        """_send should not raise when no client is connected."""
        server = _make_server()
        assert server._client is None
        # Must not raise
        await server._send({"type": "status", "text": "hello"})

    @pytest.mark.asyncio
    async def test_send_status_helper(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        await server._send_status("scanning...")
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload == {"type": "status", "text": "scanning..."}

    @pytest.mark.asyncio
    async def test_send_error_helper(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        await server._send_error("boom")
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload == {"type": "error", "text": "boom"}

    @pytest.mark.asyncio
    async def test_send_swallows_exceptions(self):
        """A broken connection must not propagate from _send."""
        server = _make_server()
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = RuntimeError("connection gone")
        server._client = mock_ws
        # Must not raise
        await server._send({"type": "status", "text": "hi"})


# ---------------------------------------------------------------------------
# _handle_command
# ---------------------------------------------------------------------------


class TestHandleCommand:
    def _server_with_controller(self) -> tuple[GrotWebSocketServer, MagicMock]:
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        mock_controller = MagicMock()
        mock_controller.transition = AsyncMock()
        mock_controller.await_current = AsyncMock()
        server._controller = mock_controller
        return server, mock_ws

    @pytest.mark.asyncio
    async def test_help_command_sends_status(self):
        server, mock_ws = self._server_with_controller()
        await server._handle_command("/help")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "status"
        assert "/help" in sent["text"]

    @pytest.mark.asyncio
    async def test_exit_command_closes_connection(self):
        server, mock_ws = self._server_with_controller()
        mock_ws.close = AsyncMock()
        await server._handle_command("/exit")
        mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_animation_command_valid(self):
        server, mock_ws = self._server_with_controller()
        from idotmatrix_upload.animations import AnimationState
        await server._handle_command("/animation idle")
        server._controller.transition.assert_called()
        # Check that the first transition call used the IDLE state
        first_call_state = server._controller.transition.call_args_list[0][0][0]
        assert first_call_state == AnimationState.IDLE

    @pytest.mark.asyncio
    async def test_animation_command_invalid_name(self):
        server, mock_ws = self._server_with_controller()
        await server._handle_command("/animation nonexistent")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "status"
        assert "Usage" in sent["text"]

    @pytest.mark.asyncio
    async def test_animation_command_missing_name(self):
        server, mock_ws = self._server_with_controller()
        await server._handle_command("/animation")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "status"
        assert "Usage" in sent["text"]

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        server, mock_ws = self._server_with_controller()
        await server._handle_command("/frobnicate")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "status"
        assert "Unknown" in sent["text"]

    @pytest.mark.asyncio
    async def test_command_without_slash_prefix_is_normalised(self):
        """Bare keywords like 'help' should be treated as '/help'."""
        server, mock_ws = self._server_with_controller()
        await server._handle_command("help")
        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "status"


# ---------------------------------------------------------------------------
# _handle_voice_audio
# ---------------------------------------------------------------------------


class TestHandleVoiceAudio:
    def _server_with_mocks(
        self,
    ) -> tuple[GrotWebSocketServer, MagicMock, MagicMock, MagicMock]:
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws

        mock_controller = MagicMock()
        mock_controller.transition = AsyncMock()
        mock_controller.await_current = AsyncMock()
        server._controller = mock_controller

        mock_session = MagicMock()
        server._session = mock_session

        mock_openai = MagicMock()
        server._openai_client = mock_openai

        return server, mock_ws, mock_controller, mock_session

    @pytest.mark.asyncio
    async def test_invalid_base64_sends_error(self):
        server, mock_ws, *_ = self._server_with_mocks()
        await server._handle_voice_audio("!!!not-base64!!!")
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_processing_flag_prevents_double_processing(self):
        server, mock_ws, *_ = self._server_with_mocks()
        server._processing = True
        await server._handle_voice_audio(_b64_wav())
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        # Should have received a "still processing" status, not an error or transcription
        assert all(m["type"] != "transcription" for m in calls)
        assert all(m["type"] != "error" for m in calls)

    @pytest.mark.asyncio
    async def test_processing_flag_reset_after_success(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()

        async def _fake_stream():
            yield "Hello "
            yield "[mood:idle]"

        mock_session.stream_response = _fake_stream
        mock_session.add_user_message = MagicMock()
        mock_session.add_assistant_message = MagicMock()

        with (
            patch(
                "idotmatrix_upload.ws_server.transcribe",
                new=AsyncMock(return_value="Hello Grot"),
            ),
            patch(
                "idotmatrix_upload.ws_server.synthesize",
                new=AsyncMock(return_value=b"\x00\x01"),
            ),
        ):
            await server._handle_voice_audio(_b64_wav())

        assert server._processing is False

    @pytest.mark.asyncio
    async def test_empty_transcription_sends_status_not_error(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()

        with patch(
            "idotmatrix_upload.ws_server.transcribe",
            new=AsyncMock(return_value=""),
        ):
            await server._handle_voice_audio(_b64_wav())

        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert not any(m["type"] == "error" for m in calls)
        assert any(
            m["type"] == "status" and "understand" in m["text"].lower()
            for m in calls
        )

    @pytest.mark.asyncio
    async def test_full_pipeline_sends_expected_message_types(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()

        async def _fake_stream():
            yield "Why "
            yield "not? "
            yield "[mood:excited]"

        mock_session.stream_response = _fake_stream
        mock_session.add_user_message = MagicMock()
        mock_session.add_assistant_message = MagicMock()

        with (
            patch(
                "idotmatrix_upload.ws_server.transcribe",
                new=AsyncMock(return_value="Tell me a joke"),
            ),
            patch(
                "idotmatrix_upload.ws_server.synthesize",
                new=AsyncMock(return_value=b"RIFF...."),
            ),
        ):
            await server._handle_voice_audio(_b64_wav())

        types = [json.loads(c[0][0])["type"] for c in mock_ws.send.call_args_list]
        assert "transcription" in types
        assert "chat_token" in types
        assert "chat_done" in types
        assert "voice_audio" in types

    @pytest.mark.asyncio
    async def test_voice_audio_response_is_base64_encoded(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()
        raw_audio = b"RIFF\x24\x00\x00\x00WAVE"

        async def _fake_stream():
            yield "hello [mood:idle]"

        mock_session.stream_response = _fake_stream
        mock_session.add_user_message = MagicMock()
        mock_session.add_assistant_message = MagicMock()

        with (
            patch(
                "idotmatrix_upload.ws_server.transcribe",
                new=AsyncMock(return_value="hi"),
            ),
            patch(
                "idotmatrix_upload.ws_server.synthesize",
                new=AsyncMock(return_value=raw_audio),
            ),
        ):
            await server._handle_voice_audio(_b64_wav())

        all_msgs = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        audio_msg = next(m for m in all_msgs if m["type"] == "voice_audio")
        decoded = base64.b64decode(audio_msg["data"])
        assert decoded == raw_audio


# ---------------------------------------------------------------------------
# _setup / _teardown
# ---------------------------------------------------------------------------


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_sends_error_when_animations_missing(self):
        server = _make_server(animations_dir=Path("/nonexistent/path"))
        mock_ws = AsyncMock()
        server._client = mock_ws

        with patch(
            "idotmatrix_upload.ws_server.AnimationRegistry.preload",
            side_effect=FileNotFoundError("missing gif"),
        ):
            result = await server._setup()

        assert result is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_setup_sends_error_when_ble_fails(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws

        with (
            patch(
                "idotmatrix_upload.ws_server.AnimationRegistry.preload",
            ),
            patch.object(
                server.__class__,
                "_setup",
                wraps=server._setup,
            ),
            patch(
                "idotmatrix_upload.ws_server.DeviceService.connect",
                new=AsyncMock(side_effect=RuntimeError("BLE scan failed")),
            ),
            patch(
                "idotmatrix_upload.ws_server.AnimationRegistry.loaded_count",
                new_callable=lambda: property(lambda self: 10),
            ),
        ):
            result = await server._setup()

        assert result is False

    @pytest.mark.asyncio
    async def test_teardown_calls_play_sleeping(self):
        server = _make_server()
        mock_controller = MagicMock()
        mock_controller.transition = AsyncMock()
        mock_controller.await_current = AsyncMock()
        mock_controller.shutdown = AsyncMock()
        server._controller = mock_controller

        mock_device = MagicMock()
        mock_device.disconnect = AsyncMock()
        server._device = mock_device

        with patch(
            "idotmatrix_upload.ws_server.play_sleeping",
            new=AsyncMock(),
        ) as mock_sleeping:
            await server._teardown()

        mock_sleeping.assert_called_once_with(mock_controller)

    @pytest.mark.asyncio
    async def test_teardown_clears_state(self):
        server = _make_server()
        mock_controller = MagicMock()
        mock_controller.shutdown = AsyncMock()
        server._controller = mock_controller
        server._session = MagicMock()
        server._openai_client = MagicMock()

        mock_device = MagicMock()
        mock_device.disconnect = AsyncMock()
        server._device = mock_device

        with patch("idotmatrix_upload.ws_server.play_sleeping", new=AsyncMock()):
            await server._teardown()

        assert server._device is None
        assert server._controller is None
        assert server._session is None
        assert server._openai_client is None
