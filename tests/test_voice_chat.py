"""Tests for voice_chat.py — highest-risk control-flow paths.

All BLE, STT, LLM, and TTS calls are mocked so tests run without hardware.
The focus is on the _voice_loop state-machine branches:
  - command mode ('/' keypress → None result)
  - empty audio capture (zero bytes)
  - empty transcription (silence) → returns to IDLE
  - successful round-trip: THINKING → TALKING → mood → IDLE
  - /help, /animation, /voice slash commands
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from walkie_grotkie.animations import AnimationState


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_registry(tmp_path: Path):
    """Create an AnimationRegistry with fake GIF files for all states."""
    from walkie_grotkie.animations import ANIMATION_MAP, AnimationRegistry

    for rel_path in ANIMATION_MAP.values():
        gif_file = tmp_path / rel_path
        gif_file.parent.mkdir(parents=True, exist_ok=True)
        gif_file.write_bytes(b"GIF89a" + b"\x00" * 50)

    registry = AnimationRegistry(tmp_path)
    registry.preload()
    return registry


def _make_device() -> MagicMock:
    device = MagicMock()
    device.send_packets = AsyncMock()
    device.address = "AA:BB:CC:DD:EE:FF"
    return device


def _make_controller(tmp_path: Path, device=None):
    from walkie_grotkie.animations import AnimationController

    device = device or _make_device()
    registry = _make_registry(tmp_path)
    transitions: list[AnimationState] = []
    controller = AnimationController(
        device, registry, on_state_change=transitions.append
    )
    return controller, transitions


# ---------------------------------------------------------------------------
# _voice_loop — empty audio capture
# ---------------------------------------------------------------------------


class TestVoiceLoopEmptyAudio:
    @pytest.mark.asyncio
    async def test_empty_wav_prints_warning_and_loops(self, tmp_path: Path):
        """When recorder returns empty bytes, loop warns and stays in current state."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, transitions = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        recorder = MagicMock()
        call_count = 0

        async def fake_wait_for_input(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b""  # empty audio
            raise KeyboardInterrupt

        recorder.wait_for_input = fake_wait_for_input

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
        ):
            try:
                await _voice_loop(console, session, controller, recorder, "test-key", "nova")
            except KeyboardInterrupt:
                pass

        # Should never have called session.add_user_message since there was no real input.
        session.add_user_message.assert_not_called()


# ---------------------------------------------------------------------------
# _voice_loop — empty transcription → IDLE
# ---------------------------------------------------------------------------


class TestVoiceLoopEmptyTranscription:
    @pytest.mark.asyncio
    async def test_silent_audio_transitions_to_idle(self, tmp_path: Path):
        """When transcription returns '', controller must go back to IDLE."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, transitions = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        recorder = MagicMock()
        call_count = 0

        async def fake_wait_for_input(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"RIFF\x00\x00\x00\x00WAVE"  # non-empty WAV bytes
            raise KeyboardInterrupt

        recorder.wait_for_input = fake_wait_for_input

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch("walkie_grotkie.voice_chat.transcribe", new_callable=AsyncMock, return_value=""),
            patch("walkie_grotkie.voice_chat.Live"),
        ):
            try:
                await _voice_loop(console, session, controller, recorder, "test-key", "nova")
            except KeyboardInterrupt:
                pass

        # IDLE must be the final state after a silent recording.
        assert controller.current_state == AnimationState.IDLE


# ---------------------------------------------------------------------------
# _voice_loop — successful full turn
# ---------------------------------------------------------------------------


class TestVoiceLoopSuccessfulTurn:
    @pytest.mark.asyncio
    async def test_full_turn_triggers_expected_animation_sequence(self, tmp_path: Path):
        """Successful voice input drives THINKING → TALKING → mood → IDLE."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, transitions = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        call_count = 0

        async def fake_wait_for_input(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"RIFF\x00\x00\x00\x00WAVE"
            raise KeyboardInterrupt

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        async def fake_stream_response():
            yield "Hello there [mood:talking]"

        session.stream_response = fake_stream_response

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch(
                "walkie_grotkie.voice_chat.transcribe",
                new_callable=AsyncMock,
                return_value="Hello Grot",
            ),
            patch(
                "walkie_grotkie.voice_chat.synthesize",
                new_callable=AsyncMock,
                return_value=b"audio",
            ),
            patch("walkie_grotkie.voice_chat.play_audio", new_callable=AsyncMock),
            patch("walkie_grotkie.voice_chat.Live"),
            patch("walkie_grotkie.voice_chat.asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                await _voice_loop(console, session, controller, recorder, "test-key", "nova")
            except KeyboardInterrupt:
                pass

        assert AnimationState.TALKING in transitions
        # After the mood the controller must end in IDLE.
        assert controller.current_state == AnimationState.IDLE

    @pytest.mark.asyncio
    async def test_user_message_added_to_session(self, tmp_path: Path):
        """Transcribed text must be added to the session history."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, _ = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        call_count = 0

        async def fake_wait_for_input(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"RIFF\x00\x00\x00\x00WAVE"
            raise KeyboardInterrupt

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        async def fake_stream_response():
            yield "Hi [mood:idle]"

        session.stream_response = fake_stream_response

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch(
                "walkie_grotkie.voice_chat.transcribe",
                new_callable=AsyncMock,
                return_value="Test input",
            ),
            patch(
                "walkie_grotkie.voice_chat.synthesize",
                new_callable=AsyncMock,
                return_value=b"audio",
            ),
            patch("walkie_grotkie.voice_chat.play_audio", new_callable=AsyncMock),
            patch("walkie_grotkie.voice_chat.Live"),
            patch("walkie_grotkie.voice_chat.asyncio.sleep", new_callable=AsyncMock),
        ):
            try:
                await _voice_loop(console, session, controller, recorder, "test-key", "nova")
            except KeyboardInterrupt:
                pass

        session.add_user_message.assert_called_with("Test input")
        session.add_assistant_message.assert_called_once()


# ---------------------------------------------------------------------------
# _voice_loop — command mode ('/' keypress)
# ---------------------------------------------------------------------------


class TestVoiceLoopCommandMode:
    @pytest.mark.asyncio
    async def test_slash_returns_none_enters_command_prompt(self, tmp_path: Path):
        """When recorder returns None (/ pressed), the loop prompts for a command."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, _ = _make_controller(tmp_path)
        session = MagicMock()

        inputs = iter([None, "/exit"])
        console = MagicMock()

        async def fake_wait_for_input(**kwargs):
            return next(inputs)

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch(
                "walkie_grotkie.voice_chat.asyncio.to_thread",
                new_callable=AsyncMock,
                return_value="/exit",
            ),
        ):
            await _voice_loop(console, session, controller, recorder, "test-key", "nova")

        # No audio processing should occur.
        session.add_user_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_slash_help_command_prints_help(self, tmp_path: Path):
        """'/help' in command mode calls the help printer."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, _ = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        call_count = 0

        async def fake_wait_for_input(**kwargs):
            nonlocal call_count
            call_count += 1
            return None if call_count == 1 else None  # always command mode

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        # First to_thread call returns '/help', second returns '/exit'
        side_effects = ["/help", "/exit"]
        side_iter = iter(side_effects)

        async def fake_to_thread(fn, *args, **kwargs):
            return next(side_iter)

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch("walkie_grotkie.voice_chat.asyncio.to_thread", side_effect=fake_to_thread),
            patch("walkie_grotkie.voice_chat._print_help") as mock_help,
        ):
            await _voice_loop(console, session, controller, recorder, "test-key", "nova")

        mock_help.assert_called_once()

    @pytest.mark.asyncio
    async def test_voice_command_changes_voice(self, tmp_path: Path):
        """'/voice shimmer' command must switch the active TTS voice."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, _ = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        # Sequence: two command rounds, then voice input, then exit
        side_effects_input = [None, None]  # two '/' presses
        input_iter = iter(side_effects_input)

        async def fake_wait_for_input(**kwargs):
            try:
                return next(input_iter)
            except StopIteration:
                raise KeyboardInterrupt

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        command_inputs = iter(["/voice shimmer", "/exit"])

        async def fake_to_thread(fn, *args, **kwargs):
            return next(command_inputs)

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch("walkie_grotkie.voice_chat.asyncio.to_thread", side_effect=fake_to_thread),
        ):
            try:
                await _voice_loop(
                    console, session, controller, recorder, "test-key", "nova"
                )
            except KeyboardInterrupt:
                pass

        # Console should have printed a voice-change confirmation.
        printed = " ".join(str(c) for c in console.print.call_args_list)
        assert "shimmer" in printed

    @pytest.mark.asyncio
    async def test_unknown_command_prints_error_message(self, tmp_path: Path):
        """Unrecognised slash commands show a useful message."""
        from walkie_grotkie.voice_chat import _voice_loop

        controller, _ = _make_controller(tmp_path)
        session = MagicMock()
        console = MagicMock()

        side_effects = [None, None]
        input_iter = iter(side_effects)

        async def fake_wait_for_input(**kwargs):
            try:
                return next(input_iter)
            except StopIteration:
                raise KeyboardInterrupt

        recorder = MagicMock()
        recorder.wait_for_input = fake_wait_for_input

        command_inputs = iter(["/unknown", "/exit"])

        async def fake_to_thread(fn, *args, **kwargs):
            return next(command_inputs)

        with (
            patch("walkie_grotkie.voice_chat.disable_terminal_echo", return_value=[]),
            patch("walkie_grotkie.voice_chat.restore_terminal"),
            patch("walkie_grotkie.voice_chat.flush_stdin"),
            patch("walkie_grotkie.voice_chat.asyncio.to_thread", side_effect=fake_to_thread),
        ):
            try:
                await _voice_loop(console, session, controller, recorder, "test-key", "nova")
            except KeyboardInterrupt:
                pass

        printed = " ".join(str(c) for c in console.print.call_args_list)
        assert "Unknown command" in printed


# ---------------------------------------------------------------------------
# _wait_for_input helper
# ---------------------------------------------------------------------------


class TestWaitForInput:
    @pytest.mark.asyncio
    async def test_thinking_transition_on_space(self, tmp_path: Path):
        """Pressing spacebar starts THINKING animation before recording."""
        from walkie_grotkie.voice_chat import _wait_for_input

        controller, transitions = _make_controller(tmp_path)
        console = MagicMock()
        recorder = MagicMock()

        async def fake_wait_for_input(on_listening=None, on_recording_stop=None):
            if on_listening:
                on_listening()
            return b"RIFF\x00\x00\x00\x00WAVE"

        recorder.wait_for_input = fake_wait_for_input

        with patch("walkie_grotkie.voice_chat.asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.create_task = lambda coro, **kwargs: asyncio.ensure_future(coro)
            await _wait_for_input(console, controller, recorder)
            await asyncio.sleep(0.05)  # let background task run

        assert AnimationState.THINKING in transitions

    @pytest.mark.asyncio
    async def test_command_returns_none(self, tmp_path: Path):
        """A '/' keypress in _wait_for_input propagates None."""
        from walkie_grotkie.voice_chat import _wait_for_input

        controller, _ = _make_controller(tmp_path)
        console = MagicMock()
        recorder = MagicMock()

        async def fake_wait_for_input(**kwargs):
            return None

        recorder.wait_for_input = fake_wait_for_input

        result = await _wait_for_input(console, controller, recorder)
        assert result is None
