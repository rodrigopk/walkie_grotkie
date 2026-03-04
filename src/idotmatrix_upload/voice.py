"""Push-to-talk audio I/O for voice chat.

Provides microphone recording (triggered by spacebar hold) and audio playback,
both implemented to be async-friendly by running blocking operations in threads.

Recording pipeline:
  pynput key listener (thread) -> asyncio.Event -> sounddevice InputStream -> WAV bytes

Playback pipeline:
  WAV bytes -> sounddevice play() (thread via asyncio.to_thread)
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

# Recording parameters
SAMPLE_RATE: int = 16_000   # Whisper works well at 16 kHz
CHANNELS: int = 1           # Mono
DTYPE: str = "int16"        # 16-bit PCM, matches WAV standard


class PushToTalkRecorder:
    """Records microphone audio while the spacebar is held.

    Uses pynput to listen for key events in a background thread. The
    recording state is communicated back to the asyncio event loop via
    threading events that are polled asynchronously.

    Usage::

        recorder = PushToTalkRecorder()
        recorder.start_listener()
        try:
            wav_bytes = await recorder.wait_and_record()
        finally:
            recorder.stop_listener()
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._press_event = asyncio.Event()
        self._release_event = asyncio.Event()
        self._listener: object | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start_listener(self) -> None:
        """Start the pynput keyboard listener in a background thread."""
        from pynput import keyboard

        self._loop = asyncio.get_event_loop()

        def on_press(key: object) -> None:
            if key == keyboard.Key.space:
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._press_event.set)

        def on_release(key: object) -> None:
            if key == keyboard.Key.space:
                if self._loop is not None:
                    self._loop.call_soon_threadsafe(self._release_event.set)

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()  # type: ignore[union-attr]
        logger.debug("Push-to-talk key listener started")

    def stop_listener(self) -> None:
        """Stop the pynput listener."""
        if self._listener is not None:
            self._listener.stop()  # type: ignore[union-attr]
            self._listener = None
            logger.debug("Push-to-talk key listener stopped")

    async def wait_and_record(
        self,
        on_listening: Callable[[], None] | None = None,
        on_recording_stop: Callable[[], None] | None = None,
    ) -> bytes:
        """Wait for spacebar press, record until release, return WAV bytes.

        Args:
            on_listening: Called immediately when spacebar is pressed (recording starts).
            on_recording_stop: Called when spacebar is released (recording stops).

        Returns:
            WAV-formatted audio bytes ready to send to the STT API.
        """
        self._press_event.clear()
        self._release_event.clear()

        await self._press_event.wait()
        if on_listening is not None:
            on_listening()

        frames: list[np.ndarray] = []

        def audio_callback(
            indata: np.ndarray,
            frame_count: int,
            time_info: object,
            status: sd.CallbackFlags,
        ) -> None:
            if status:
                logger.debug("Audio callback status: %s", status)
            frames.append(indata.copy())

        with sd.InputStream(
            samplerate=self._sample_rate,
            channels=CHANNELS,
            dtype=DTYPE,
            callback=audio_callback,
        ):
            await self._release_event.wait()

        if on_recording_stop is not None:
            on_recording_stop()

        logger.debug("Recorded %d audio frames", len(frames))
        return _frames_to_wav(frames, self._sample_rate)


def _frames_to_wav(frames: list[np.ndarray], sample_rate: int) -> bytes:
    """Convert a list of PCM numpy arrays into WAV bytes."""
    if not frames:
        audio_data = np.zeros((0,), dtype=np.int16)
    else:
        audio_data = np.concatenate(frames, axis=0)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    return buf.getvalue()


async def play_audio(audio_bytes: bytes) -> None:
    """Play audio bytes through the default output device.

    Runs the blocking sounddevice call in a thread pool executor so the
    asyncio event loop is not blocked during playback.

    Args:
        audio_bytes: WAV or PCM audio data to play.
    """
    await asyncio.to_thread(_play_audio_sync, audio_bytes)


def _play_audio_sync(audio_bytes: bytes) -> None:
    """Blocking audio playback — runs in a thread."""
    buf = io.BytesIO(audio_bytes)
    try:
        with wave.open(buf, "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
    except wave.Error:
        # If not a valid WAV file, treat as raw PCM at default rate
        logger.warning("Audio data is not valid WAV; playing as raw PCM")
        raw = audio_bytes
        sample_rate = SAMPLE_RATE
        n_channels = CHANNELS

    audio_array = np.frombuffer(raw, dtype=np.int16).reshape(-1, n_channels)
    sd.play(audio_array, samplerate=sample_rate)
    sd.wait()
    logger.debug("Audio playback complete (%d bytes)", len(audio_bytes))
