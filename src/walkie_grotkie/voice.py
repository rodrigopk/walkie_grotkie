"""Push-to-talk audio I/O for voice chat.

Provides microphone recording (triggered by spacebar hold) and audio playback,
both implemented to be async-friendly by running blocking operations in threads.

Recording pipeline:
  pynput key listener (thread) -> asyncio.Event -> sounddevice InputStream -> WAV bytes

Playback pipeline:
  WAV bytes -> sounddevice play() (thread via asyncio.to_thread)

Terminal echo control:
  disable_terminal_echo / restore_terminal use termios to suppress key echo while
  the push-to-talk loop is waiting, preventing stray spaces and slash characters
  from appearing in the terminal output.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import sys
import wave
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

# Recording parameters
SAMPLE_RATE: int = 16_000   # Whisper works well at 16 kHz
CHANNELS: int = 1           # Mono
DTYPE: str = "int16"        # 16-bit PCM, matches WAV standard


# ---------------------------------------------------------------------------
# Terminal echo helpers (macOS / Linux via termios)
# ---------------------------------------------------------------------------

def disable_terminal_echo() -> list:
    """Disable terminal echo on stdin and return the old termios settings.

    Call restore_terminal() with the returned value to re-enable echo.
    Returns an empty list on platforms that do not support termios (e.g. Windows).
    """
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return old
    except (ImportError, OSError, AttributeError):
        # termios is unavailable (Windows) or stdin is not a real tty.
        return []


def restore_terminal(old_settings: list) -> None:
    """Restore terminal settings saved by disable_terminal_echo().

    A no-op if old_settings is empty (non-termios platforms).
    """
    if not old_settings:
        return
    try:
        import termios
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (ImportError, OSError, AttributeError):
        pass


def flush_stdin() -> None:
    """Discard any unread characters buffered on stdin."""
    try:
        import termios
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (ImportError, OSError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Focus detection (macOS)
# ---------------------------------------------------------------------------

def _build_ancestor_pids() -> set[int]:
    """Return the set of PIDs from the current process up to PID 1.

    Called once at listener startup so the cost of shelling out to ``ps``
    is only paid once.
    """
    pids: set[int] = set()
    current = os.getpid()
    while current > 0:
        pids.add(current)
        try:
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-p", str(current)],
                capture_output=True, text=True, timeout=1,
            )
            ppid = int(result.stdout.strip())
            if ppid <= 0 or ppid == current or ppid in pids:
                break
            current = ppid
        except (subprocess.TimeoutExpired, ValueError, OSError):
            break
    return pids


def _is_terminal_focused(ancestor_pids: set[int]) -> bool:
    """Return True if the frontmost macOS app is an ancestor of this process.

    Falls back to True on non-macOS platforms or when detection fails,
    so input is never silently swallowed on unsupported systems.
    """
    if sys.platform != "darwin" or not ancestor_pids:
        return True
    try:
        from AppKit import NSWorkspace  # type: ignore[import-untyped]

        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        return front.processIdentifier() in ancestor_pids
    except Exception:
        return True


# ---------------------------------------------------------------------------
# PushToTalkRecorder
# ---------------------------------------------------------------------------

class PushToTalkRecorder:
    """Records microphone audio while the spacebar is held.

    Uses pynput to listen for key events in a background thread. The
    recording state is communicated back to the asyncio event loop via
    threading events that are polled asynchronously.

    Also detects '/' keypresses so the voice loop can offer slash commands
    without leaving echo control mode.

    Usage::

        recorder = PushToTalkRecorder()
        recorder.start_listener()
        try:
            result = await recorder.wait_for_input()
            if result is None:
                # '/' was pressed — handle command
                pass
            else:
                # spacebar was pressed-and-released — result is WAV bytes
                process(result)
        finally:
            recorder.stop_listener()
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._press_event = asyncio.Event()
        self._release_event = asyncio.Event()
        self._command_event = asyncio.Event()
        self._space_held: bool = False
        self._listener: object | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ancestor_pids: set[int] = set()

    def start_listener(self) -> None:
        """Start the pynput keyboard listener in a background thread."""
        from pynput import keyboard

        self._loop = asyncio.get_event_loop()
        self._ancestor_pids = _build_ancestor_pids()

        def on_press(key: object) -> None:
            if not _is_terminal_focused(self._ancestor_pids):
                return
            if key == keyboard.Key.space:
                if not self._space_held:
                    self._space_held = True
                    if self._loop is not None:
                        self._loop.call_soon_threadsafe(self._press_event.set)
            else:
                try:
                    char = key.char  # type: ignore[union-attr]
                except AttributeError:
                    char = None
                if char == "/" and self._loop is not None:
                    self._loop.call_soon_threadsafe(self._command_event.set)

        def on_release(key: object) -> None:
            if key == keyboard.Key.space:
                self._space_held = False
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

    async def wait_for_input(
        self,
        on_listening: Callable[[], None] | None = None,
        on_recording_stop: Callable[[], None] | None = None,
    ) -> bytes | None:
        """Wait for either a spacebar press (record) or a '/' keypress (command).

        Returns WAV bytes if the user pressed and released the spacebar.
        Returns None if the user pressed '/' to enter command mode.

        Args:
            on_listening: Called immediately when spacebar press is detected.
            on_recording_stop: Called when spacebar is released.
        """
        self._press_event.clear()
        self._release_event.clear()
        self._command_event.clear()
        self._space_held = False

        space_task = asyncio.ensure_future(self._press_event.wait())
        cmd_task = asyncio.ensure_future(self._command_event.wait())

        done, pending = await asyncio.wait(
            {space_task, cmd_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()

        if cmd_task in done:
            return None

        # Spacebar won — record until release.
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
        self._space_held = False

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
