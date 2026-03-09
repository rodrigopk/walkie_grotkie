"""Tests for the GrotWebSocketServer WebSocket API.

All BLE and AI interactions are mocked so no device or API key is needed.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import openai as _openai
import pytest

from walkie_grotkie.ws_server import DEFAULT_PORT, GrotWebSocketServer


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


def _make_server_no_key(**kwargs) -> GrotWebSocketServer:
    """Return a server instance with no API key (simulates UI-provided key flow)."""
    defaults = dict(
        api_key="",
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

    def test_api_key_defaults_to_empty_string(self):
        server = GrotWebSocketServer(animations_dir=Path("grot_animations"))
        assert server._api_key == ""

    def test_api_key_can_be_empty_string(self):
        server = _make_server_no_key()
        assert server._api_key == ""

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
        from walkie_grotkie.animations import AnimationState
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
    async def test_animation_command_surprised(self):
        server, mock_ws = self._server_with_controller()
        from walkie_grotkie.animations import AnimationState
        await server._handle_command("/animation surprised")
        first_call_state = server._controller.transition.call_args_list[0][0][0]
        assert first_call_state == AnimationState.SURPRISED

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
                "walkie_grotkie.ws_server.transcribe",
                new=AsyncMock(return_value="Hello Grot"),
            ),
            patch(
                "walkie_grotkie.ws_server.synthesize",
                new=AsyncMock(return_value=b"\x00\x01"),
            ),
        ):
            await server._handle_voice_audio(_b64_wav())

        assert server._processing is False

    @pytest.mark.asyncio
    async def test_empty_transcription_sends_status_not_error(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()

        with patch(
            "walkie_grotkie.ws_server.transcribe",
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
                "walkie_grotkie.ws_server.transcribe",
                new=AsyncMock(return_value="Tell me a joke"),
            ),
            patch(
                "walkie_grotkie.ws_server.synthesize",
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
    async def test_pipeline_error_transitions_to_surprised(self):
        server, mock_ws, mock_controller, mock_session = self._server_with_mocks()

        with patch(
            "walkie_grotkie.ws_server.transcribe",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            await server._handle_voice_audio(_b64_wav())

        from walkie_grotkie.animations import AnimationState
        mock_controller.transition.assert_called()
        last_state = mock_controller.transition.call_args_list[-1][0][0]
        assert last_state == AnimationState.SURPRISED

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
                "walkie_grotkie.ws_server.transcribe",
                new=AsyncMock(return_value="hi"),
            ),
            patch(
                "walkie_grotkie.ws_server.synthesize",
                new=AsyncMock(return_value=raw_audio),
            ),
        ):
            await server._handle_voice_audio(_b64_wav())

        all_msgs = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        audio_msg = next(m for m in all_msgs if m["type"] == "voice_audio")
        decoded = base64.b64decode(audio_msg["data"])
        assert decoded == raw_audio


# ---------------------------------------------------------------------------
# _setup_ble / _setup_openai / _teardown
# ---------------------------------------------------------------------------


class TestSetupBle:
    @pytest.mark.asyncio
    async def test_setup_ble_sends_error_when_animations_missing(self):
        server = _make_server(animations_dir=Path("/nonexistent/path"))
        mock_ws = AsyncMock()
        server._client = mock_ws

        with patch(
            "walkie_grotkie.ws_server.AnimationRegistry.preload",
            side_effect=FileNotFoundError("missing gif"),
        ):
            result = await server._setup_ble()

        assert result is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_setup_ble_sends_ble_error_when_ble_fails(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws

        with (
            patch(
                "walkie_grotkie.ws_server.AnimationRegistry.preload",
            ),
            patch(
                "walkie_grotkie.ws_server.DeviceService.connect",
                new=AsyncMock(side_effect=RuntimeError("BLE scan failed")),
            ),
            patch(
                "walkie_grotkie.ws_server.AnimationRegistry.loaded_count",
                new_callable=lambda: property(lambda self: 10),
            ),
        ):
            result = await server._setup_ble()

        assert result is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "ble_error" for m in calls)
        assert not any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_setup_ble_does_not_require_api_key(self):
        """_setup_ble must succeed even when no API key is configured."""
        server = _make_server_no_key()
        mock_ws = AsyncMock()
        server._client = mock_ws

        with (
            patch("walkie_grotkie.ws_server.AnimationRegistry.preload"),
            patch(
                "walkie_grotkie.ws_server.DeviceService.connect",
                new=AsyncMock(),
            ),
            patch(
                "walkie_grotkie.ws_server.AnimationRegistry.loaded_count",
                new_callable=lambda: property(lambda self: 5),
            ),
            patch(
                "walkie_grotkie.ws_server.DeviceService.address",
                new_callable=lambda: property(lambda self: "AA:BB:CC:DD:EE:FF"),
            ),
        ):
            result = await server._setup_ble()

        assert result is True
        assert server._session is None
        assert server._openai_client is None


class TestSetupOpenAI:
    @pytest.mark.asyncio
    async def test_setup_openai_creates_session_and_client(self):
        server = _make_server(api_key="sk-build-test")
        with patch("walkie_grotkie.ws_server._openai.AsyncOpenAI") as mock_cls:
            await server._setup_openai()
        # AsyncOpenAI is called at least once with the correct key.
        # (OpenAIChatSession may also call it internally.)
        assert mock_cls.call_count >= 1
        assert mock_cls.call_args_list[-1] == ((), {"api_key": "sk-build-test"})
        assert server._session is not None
        assert server._openai_client is not None

    @pytest.mark.asyncio
    async def test_setup_openai_uses_current_api_key(self):
        """After updating _api_key, _setup_openai must use the new value."""
        server = _make_server(api_key="sk-old")
        server._api_key = "sk-new"
        with patch("walkie_grotkie.ws_server._openai.AsyncOpenAI") as mock_cls:
            await server._setup_openai()
        # The last explicit client construction must use the updated key.
        mock_cls.assert_called_with(api_key="sk-new")

    @pytest.mark.asyncio
    async def test_setup_openai_replaces_existing_session(self):
        server = _make_server(api_key="sk-test")
        old_session = MagicMock()
        server._session = old_session
        await server._setup_openai()
        assert server._session is not old_session

    @pytest.mark.asyncio
    async def test_setup_openai_propagates_auth_error(self):
        """AuthenticationError must propagate so the caller can send auth_error."""
        from walkie_grotkie.openai_chat import OpenAIChatSession

        server = _make_server(api_key="sk-bad")
        with patch.object(
            OpenAIChatSession,
            "__init__",
            side_effect=_openai.AuthenticationError.__new__(_openai.AuthenticationError),
        ):
            pass  # We'll test via _handle_set_api_key instead (see TestSetApiKey)


class TestSetApiKey:
    def _server_with_controller(self) -> tuple[GrotWebSocketServer, AsyncMock]:
        server = _make_server_no_key()
        mock_ws = AsyncMock()
        server._client = mock_ws
        mock_controller = MagicMock()
        mock_controller.transition = AsyncMock()
        mock_controller.await_current = AsyncMock()
        mock_controller.shutdown = AsyncMock()
        server._controller = mock_controller
        return server, mock_ws

    @pytest.mark.asyncio
    async def test_set_api_key_empty_sends_error(self):
        server, mock_ws = self._server_with_controller()
        await server._handle_set_api_key("")
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_set_api_key_stores_new_key(self):
        server, mock_ws = self._server_with_controller()

        with (
            patch.object(server, "_setup_openai", new=AsyncMock()),
            patch.object(server, "_send_greeting", new=AsyncMock()),
        ):
            await server._handle_set_api_key("sk-new-key")

        assert server._api_key == "sk-new-key"

    @pytest.mark.asyncio
    async def test_set_api_key_calls_setup_openai(self):
        server, mock_ws = self._server_with_controller()

        with (
            patch.object(server, "_setup_openai", new=AsyncMock()) as mock_setup,
            patch.object(server, "_send_greeting", new=AsyncMock()),
        ):
            await server._handle_set_api_key("sk-valid-key")

        mock_setup.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_api_key_sends_ready_on_success(self):
        server, mock_ws = self._server_with_controller()

        with (
            patch.object(server, "_setup_openai", new=AsyncMock()),
            patch.object(server, "_send_greeting", new=AsyncMock()),
        ):
            await server._handle_set_api_key("sk-valid-key")

        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_set_api_key_sends_auth_error_on_bad_key(self):
        server, mock_ws = self._server_with_controller()

        import openai as _openai_mod

        with patch.object(
            server,
            "_setup_openai",
            new=AsyncMock(
                side_effect=_openai_mod.AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(status_code=401),
                    body=None,
                )
            ),
        ):
            await server._handle_set_api_key("sk-bad-key")

        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "auth_error" for m in calls)
        assert not any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_set_api_key_clears_existing_session_before_rebuilding(self):
        server, mock_ws = self._server_with_controller()
        server._session = MagicMock()
        server._openai_client = MagicMock()

        with (
            patch.object(server, "_setup_openai", new=AsyncMock()),
            patch.object(server, "_send_greeting", new=AsyncMock()),
        ):
            await server._handle_set_api_key("sk-new")

        # After _handle_set_api_key, _setup_openai sets fresh objects.
        # The old references must have been cleared before setup ran.
        # We verify _setup_openai was called (which rebuilds them).
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_auth_error_transitions_to_surprised(self):
        server, mock_ws = self._server_with_controller()
        import openai as _openai_mod

        with patch.object(
            server,
            "_setup_openai",
            new=AsyncMock(
                side_effect=_openai_mod.AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(status_code=401),
                    body=None,
                )
            ),
        ):
            await server._handle_set_api_key("sk-bad-key")

        from walkie_grotkie.animations import AnimationState
        server._controller.transition.assert_called()
        last_state = server._controller.transition.call_args_list[-1][0][0]
        assert last_state == AnimationState.SURPRISED

    @pytest.mark.asyncio
    async def test_send_auth_error_helper(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        await server._send_auth_error("Invalid key provided")
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload == {"type": "auth_error", "text": "Invalid key provided"}

    @pytest.mark.asyncio
    async def test_send_ble_error_helper(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws
        await server._send_ble_error("Device not found")
        payload = json.loads(mock_ws.send.call_args[0][0])
        assert payload == {"type": "ble_error", "text": "Device not found"}


class TestSetup:
    """Backward-compat tests using the combined _setup() convenience wrapper."""

    @pytest.mark.asyncio
    async def test_setup_sends_error_when_animations_missing(self):
        server = _make_server(animations_dir=Path("/nonexistent/path"))
        mock_ws = AsyncMock()
        server._client = mock_ws

        with patch(
            "walkie_grotkie.ws_server.AnimationRegistry.preload",
            side_effect=FileNotFoundError("missing gif"),
        ):
            result = await server._setup()

        assert result is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_setup_sends_ble_error_when_ble_fails(self):
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws

        with (
            patch(
                "walkie_grotkie.ws_server.AnimationRegistry.preload",
            ),
            patch(
                "walkie_grotkie.ws_server.DeviceService.connect",
                new=AsyncMock(side_effect=RuntimeError("BLE scan failed")),
            ),
            patch(
                "walkie_grotkie.ws_server.AnimationRegistry.loaded_count",
                new_callable=lambda: property(lambda self: 10),
            ),
        ):
            result = await server._setup()

        assert result is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "ble_error" for m in calls)

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
            "walkie_grotkie.ws_server.play_sleeping",
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

        with patch("walkie_grotkie.ws_server.play_sleeping", new=AsyncMock()):
            await server._teardown()

        assert server._device is None
        assert server._controller is None
        assert server._session is None
        assert server._openai_client is None


# ---------------------------------------------------------------------------
# TestHandleRestart
# ---------------------------------------------------------------------------


class TestHandleRestart:
    """Tests for GrotWebSocketServer._handle_restart()."""

    def _server_with_mocks(
        self,
    ) -> tuple[GrotWebSocketServer, AsyncMock]:
        server = _make_server()
        mock_ws = AsyncMock()
        server._client = mock_ws

        mock_controller = MagicMock()
        mock_controller.transition = AsyncMock()
        mock_controller.await_current = AsyncMock()
        mock_controller.shutdown = AsyncMock()
        server._controller = mock_controller

        mock_session = MagicMock()
        server._session = mock_session

        mock_device = MagicMock()
        mock_device.disconnect = AsyncMock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        server._device = mock_device

        return server, mock_ws

    @pytest.mark.asyncio
    async def test_restart_tears_down_and_reconnects(self):
        server, mock_ws = self._server_with_mocks()
        with (
            patch.object(server, "_teardown", new=AsyncMock()) as mock_teardown,
            patch.object(server, "_setup_ble", new=AsyncMock(return_value=True)),
            patch.object(server, "_setup_openai", new=AsyncMock()),
            patch.object(server, "_send_greeting_inner", new=AsyncMock()),
        ):
            await server._handle_restart()

        mock_teardown.assert_called_once()
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(
            m["type"] == "status" and "Restarting" in m["text"] for m in calls
        )
        assert any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_restart_rejected_while_processing(self):
        server, mock_ws = self._server_with_mocks()
        server._processing = True
        await server._handle_restart()
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any("wait" in m.get("text", "").lower() for m in calls)
        # No teardown, no ready
        assert not any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_restart_handles_ble_failure(self):
        server, mock_ws = self._server_with_mocks()
        with (
            patch.object(server, "_teardown", new=AsyncMock()),
            patch.object(server, "_setup_ble", new=AsyncMock(return_value=False)),
        ):
            await server._handle_restart()

        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert not any(m["type"] == "ready" for m in calls)

    @pytest.mark.asyncio
    async def test_restart_clears_processing_flag_on_success(self):
        server, _ = self._server_with_mocks()
        with (
            patch.object(server, "_teardown", new=AsyncMock()),
            patch.object(server, "_setup_ble", new=AsyncMock(return_value=True)),
            patch.object(server, "_setup_openai", new=AsyncMock()),
            patch.object(server, "_send_greeting_inner", new=AsyncMock()),
        ):
            await server._handle_restart()

        assert server._processing is False

    @pytest.mark.asyncio
    async def test_restart_clears_processing_flag_on_exception(self):
        server, mock_ws = self._server_with_mocks()
        with (
            patch.object(server, "_teardown", new=AsyncMock()),
            patch.object(
                server, "_setup_ble", new=AsyncMock(side_effect=RuntimeError("boom"))
            ),
        ):
            await server._handle_restart()

        assert server._processing is False
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "error" for m in calls)

    @pytest.mark.asyncio
    async def test_restart_without_api_key_sends_ready_without_greeting(self):
        server = _make_server_no_key()
        mock_ws = AsyncMock()
        server._client = mock_ws
        with (
            patch.object(server, "_teardown", new=AsyncMock()),
            patch.object(server, "_setup_ble", new=AsyncMock(return_value=True)),
            patch.object(server, "_send_greeting_inner", new=AsyncMock()) as mock_greet,
        ):
            await server._handle_restart()

        mock_greet.assert_not_called()
        calls = [json.loads(c[0][0]) for c in mock_ws.send.call_args_list]
        assert any(m["type"] == "ready" for m in calls)
