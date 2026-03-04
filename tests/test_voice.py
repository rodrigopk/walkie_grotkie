"""Tests for voice.py — PushToTalkRecorder and play_audio."""

from __future__ import annotations

import asyncio
import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from idotmatrix_upload.voice import (
    CHANNELS,
    SAMPLE_RATE,
    _frames_to_wav,
    _play_audio_sync,
    play_audio,
)


# ---------------------------------------------------------------------------
# _frames_to_wav (pure conversion, no I/O)
# ---------------------------------------------------------------------------


class TestFramesToWav:
    def test_returns_valid_wav_header(self):
        frames = [np.zeros((1024,), dtype=np.int16)]
        wav_bytes = _frames_to_wav(frames, SAMPLE_RATE)
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_wav_sample_rate_matches(self):
        frames = [np.zeros((1024,), dtype=np.int16)]
        wav_bytes = _frames_to_wav(frames, SAMPLE_RATE)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == SAMPLE_RATE

    def test_wav_channels_match(self):
        frames = [np.zeros((512,), dtype=np.int16)]
        wav_bytes = _frames_to_wav(frames, SAMPLE_RATE)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnchannels() == CHANNELS

    def test_empty_frames_produces_valid_wav(self):
        wav_bytes = _frames_to_wav([], SAMPLE_RATE)
        assert wav_bytes[:4] == b"RIFF"
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnframes() == 0

    def test_multiple_frames_concatenated(self):
        frames = [
            np.ones((256,), dtype=np.int16),
            np.ones((256,), dtype=np.int16) * 2,
        ]
        wav_bytes = _frames_to_wav(frames, SAMPLE_RATE)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnframes() == 512

    def test_audio_data_roundtrips(self):
        original = np.array([100, 200, 300, 400], dtype=np.int16)
        wav_bytes = _frames_to_wav([original], SAMPLE_RATE)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        recovered = np.frombuffer(raw, dtype=np.int16)
        np.testing.assert_array_equal(recovered, original)

    def test_custom_sample_rate(self):
        frames = [np.zeros((512,), dtype=np.int16)]
        wav_bytes = _frames_to_wav(frames, 44100)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 44100


# ---------------------------------------------------------------------------
# _play_audio_sync — blocking playback (mocked sounddevice)
# ---------------------------------------------------------------------------


class TestPlayAudioSync:
    def _make_wav(self, n_samples: int = 1024) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(np.zeros(n_samples, dtype=np.int16).tobytes())
        return buf.getvalue()

    def test_calls_sd_play_and_wait(self):
        wav = self._make_wav()
        with (
            patch("idotmatrix_upload.voice.sd.play") as mock_play,
            patch("idotmatrix_upload.voice.sd.wait") as mock_wait,
        ):
            _play_audio_sync(wav)
            mock_play.assert_called_once()
            mock_wait.assert_called_once()

    def test_play_called_with_correct_sample_rate(self):
        wav = self._make_wav()
        with (
            patch("idotmatrix_upload.voice.sd.play") as mock_play,
            patch("idotmatrix_upload.voice.sd.wait"),
        ):
            _play_audio_sync(wav)
            _, kwargs = mock_play.call_args
            assert kwargs.get("samplerate") == SAMPLE_RATE or mock_play.call_args[1].get("samplerate") == SAMPLE_RATE

    def test_plays_audio_array_with_correct_shape(self):
        n_samples = 512
        wav = self._make_wav(n_samples)
        played_array = None

        def capture_play(arr, **kwargs):
            nonlocal played_array
            played_array = arr

        with (
            patch("idotmatrix_upload.voice.sd.play", side_effect=capture_play),
            patch("idotmatrix_upload.voice.sd.wait"),
        ):
            _play_audio_sync(wav)

        assert played_array is not None
        assert played_array.shape == (n_samples, 1)
        assert played_array.dtype == np.int16


# ---------------------------------------------------------------------------
# play_audio — async wrapper
# ---------------------------------------------------------------------------


class TestPlayAudio:
    @pytest.mark.asyncio
    async def test_play_audio_runs_sync_in_thread(self):
        """play_audio() should delegate to _play_audio_sync in a thread."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"\x00" * 1024)
        wav = buf.getvalue()

        with patch("idotmatrix_upload.voice._play_audio_sync") as mock_sync:
            await play_audio(wav)
            mock_sync.assert_called_once_with(wav)

    @pytest.mark.asyncio
    async def test_play_audio_does_not_block_event_loop(self):
        """Other tasks should run while audio plays (thread offload check)."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"\x00" * 512)
        wav = buf.getvalue()

        side_task_ran = False

        async def side_task():
            nonlocal side_task_ran
            await asyncio.sleep(0)
            side_task_ran = True

        with patch("idotmatrix_upload.voice._play_audio_sync"):
            await asyncio.gather(play_audio(wav), side_task())

        assert side_task_ran


# ---------------------------------------------------------------------------
# PushToTalkRecorder — wait_and_record (mocked pynput + sounddevice)
# ---------------------------------------------------------------------------


def _make_recorder_with_fresh_events():
    """Return a PushToTalkRecorder with fresh asyncio Events (no listener started)."""
    from idotmatrix_upload.voice import PushToTalkRecorder
    recorder = PushToTalkRecorder()
    recorder._press_event = asyncio.Event()
    recorder._release_event = asyncio.Event()
    return recorder


async def _trigger_events(recorder, delay: float = 0.01) -> None:
    """Yield once so wait_and_record starts, then fire press and release.

    wait_and_record() calls .clear() on both events at startup, so we must
    trigger them AFTER the method has started awaiting, not before.
    """
    await asyncio.sleep(delay)
    recorder._press_event.set()
    await asyncio.sleep(delay)
    recorder._release_event.set()


class _NoOpInputStream:
    """Minimal sounddevice.InputStream stand-in that never touches hardware."""
    def __init__(self, **kwargs):
        self._callback = kwargs.get("callback")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _CallbackInputStream(_NoOpInputStream):
    """InputStream that fires the audio callback once on enter with fake samples."""
    def __init__(self, frames, **kwargs):
        super().__init__(**kwargs)
        self._frames = frames

    def __enter__(self):
        if self._callback and self._frames:
            self._callback(
                self._frames[0].reshape(-1, 1),
                len(self._frames[0]),
                None,
                MagicMock(),
            )
        return self


class TestPushToTalkRecorder:
    @pytest.mark.asyncio
    async def test_records_and_returns_wav(self):
        """Simulate spacebar press+release and verify WAV bytes are returned."""
        recorder = _make_recorder_with_fresh_events()
        sample_frames = [np.zeros((512,), dtype=np.int16)]

        def make_stream(**kwargs):
            return _CallbackInputStream(sample_frames, **kwargs)

        with patch("idotmatrix_upload.voice.sd.InputStream", make_stream):
            wav_bytes, _ = await asyncio.gather(
                recorder.wait_and_record(),
                _trigger_events(recorder),
            )

        assert wav_bytes[:4] == b"RIFF"
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wf:
            assert wf.getnframes() > 0

    @pytest.mark.asyncio
    async def test_on_listening_callback_called(self):
        recorder = _make_recorder_with_fresh_events()
        called = []

        with patch("idotmatrix_upload.voice.sd.InputStream", _NoOpInputStream):
            await asyncio.gather(
                recorder.wait_and_record(on_listening=lambda: called.append(True)),
                _trigger_events(recorder),
            )

        assert called == [True]

    @pytest.mark.asyncio
    async def test_on_recording_stop_callback_called(self):
        recorder = _make_recorder_with_fresh_events()
        stopped = []

        with patch("idotmatrix_upload.voice.sd.InputStream", _NoOpInputStream):
            await asyncio.gather(
                recorder.wait_and_record(on_recording_stop=lambda: stopped.append(True)),
                _trigger_events(recorder),
            )

        assert stopped == [True]
