"""Animation state machine, preloading registry, and BLE upload controller.

Maps conversation phases (idle, thinking, talking, etc.) to pre-built
protocol packets that can be pushed to the iDotMatrix device with
cancellation support for rapid state transitions.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path

from . import protocol
from .service import DeviceService

logger = logging.getLogger(__name__)


class AnimationState(Enum):
    IDLE = auto()
    THINKING = auto()
    TALKING = auto()
    TALKING_ALT = auto()
    EXCITED = auto()
    DANCING = auto()

ANIMATION_MAP: dict[AnimationState, str] = {
    AnimationState.IDLE:        "grot-antenna/grot-antenna.gif",
    AnimationState.THINKING:    "grot-dance/grot-dance.gif",
    AnimationState.TALKING:     "grot-talking/grot-talking.gif",
    AnimationState.TALKING_ALT: "grot-talking-2/grot-talking-2.gif",
    AnimationState.EXCITED:     "grot-jump-flip/grot-jump-flip.gif",
    AnimationState.DANCING:     "grot-dance/grot-dance.gif",
}


class AnimationRegistry:
    """Preloads GIF files and pre-builds protocol packets at startup.

    Avoids filesystem reads and packet construction during the chat loop.
    """

    def __init__(self, animations_dir: Path) -> None:
        self._animations_dir = animations_dir
        self._packets: dict[AnimationState, list[bytes]] = {}

    def preload(self, chunk_size: int = protocol.DEFAULT_CHUNK_SIZE) -> None:
        """Read every mapped GIF and build protocol packets.

        Raises:
            FileNotFoundError: If a mapped GIF file is missing.
        """
        for state, rel_path in ANIMATION_MAP.items():
            gif_path = self._animations_dir / rel_path
            if not gif_path.exists():
                raise FileNotFoundError(
                    f"Animation GIF not found: {gif_path}. "
                    f"Make sure the grot_animations directory is complete."
                )
            gif_data = gif_path.read_bytes()
            self._packets[state] = protocol.build_packets(gif_data, chunk_size)
            logger.info(
                "Preloaded %s (%d bytes, %d packets)",
                state.name, len(gif_data), len(self._packets[state]),
            )

    def get_packets(self, state: AnimationState) -> list[bytes]:
        """Return pre-built packets for the given state.

        Raises:
            KeyError: If preload() was not called or the state is unmapped.
        """
        return self._packets[state]

    @property
    def loaded_count(self) -> int:
        return len(self._packets)


class AnimationController:
    """Manages animation state transitions with background upload and cancellation.

    Only one upload runs at a time.  When a new state arrives mid-upload,
    the in-flight upload task is cancelled before starting the next one.
    """

    def __init__(
        self,
        device: DeviceService,
        registry: AnimationRegistry,
        on_state_change: Callable[[AnimationState], None] | None = None,
    ) -> None:
        self._device = device
        self._registry = registry
        self._on_state_change = on_state_change
        self._current_state: AnimationState | None = None
        self._current_task: asyncio.Task[None] | None = None

    @property
    def current_state(self) -> AnimationState | None:
        return self._current_state

    async def transition(self, new_state: AnimationState) -> None:
        """Transition to a new animation state.

        Cancels any in-flight upload, then starts sending the new animation
        in a background task.  No-ops if already in the requested state.
        """
        if new_state == self._current_state:
            return

        await self._cancel_current()
        self._current_state = new_state

        if self._on_state_change is not None:
            self._on_state_change(new_state)

        packets = self._registry.get_packets(new_state)
        self._current_task = asyncio.create_task(
            self._send(packets, new_state),
            name=f"animation-{new_state.name}",
        )

    async def _send(self, packets: list[bytes], state: AnimationState) -> None:
        try:
            await self._device.send_packets(packets)
            logger.debug("Animation upload complete: %s", state.name)
        except asyncio.CancelledError:
            logger.debug("Animation upload cancelled: %s", state.name)
        except Exception:
            logger.exception("Animation upload failed: %s", state.name)

    async def _cancel_current(self) -> None:
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            self._current_task = None

    async def shutdown(self) -> None:
        """Cancel any in-flight upload.  Call before disconnecting."""
        await self._cancel_current()
