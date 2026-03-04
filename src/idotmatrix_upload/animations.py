"""Animation state machine, preloading registry, and BLE upload controller.

Maps conversation phases (idle, thinking, talking, etc.) to pre-built
protocol packets that can be pushed to the iDotMatrix device with
cancellation support for rapid state transitions.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from enum import Enum, auto
from pathlib import Path

from . import protocol
from .service import DeviceService

logger = logging.getLogger(__name__)

ANIMATION_DURATION_S: float = 1.8
DANCING_SPIN_DURATION_S: float = 2.5  # grot-spin: 50 frames at 20 fps


class AnimationState(Enum):
    IDLE = auto()
    IDLE_ALT = auto()
    THINKING = auto()
    TALKING = auto()
    TALKING_ALT = auto()
    EXCITED = auto()
    DANCING = auto()
    DANCING_ALT = auto()
    DANCING_FLIP = auto()

ANIMATION_MAP: dict[AnimationState, str] = {
    AnimationState.IDLE:         "grot-idle-3/grot-idle-3.gif",
    AnimationState.IDLE_ALT:     "grot-idle-4/grot-idle-4.gif",
    AnimationState.THINKING:     "grot-antenna/grot-antenna.gif",
    AnimationState.TALKING:      "grot-talking/grot-talking.gif",
    AnimationState.TALKING_ALT:  "grot-talking-2/grot-talking-2.gif",
    AnimationState.EXCITED:      "grot-jump-flip/grot-jump-flip.gif",
    AnimationState.DANCING:      "grot-spin/grot-spin.gif",
    AnimationState.DANCING_ALT:  "grot-dance/grot-dance.gif",
    AnimationState.DANCING_FLIP: "grot-flip/grot-flip.gif",
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

        For TALKING, a random sequence is chosen each time from:
          - grot-talking only
          - grot-talking-2 only
          - grot-talking followed by grot-talking-2 (with a timed gap)

        For DANCING, a random sequence is chosen each time from:
          - grot-spin only
          - grot-dance only
          - grot-spin followed by grot-dance (with a timed gap)
        """
        if new_state == self._current_state:
            return

        await self._cancel_current()
        self._current_state = new_state

        if self._on_state_change is not None:
            self._on_state_change(new_state)

        if new_state == AnimationState.TALKING:
            sequence = self._pick_talking_sequence()
            self._current_task = asyncio.create_task(
                self._send_sequence(sequence, new_state),
                name=f"animation-{new_state.name}",
            )
        elif new_state == AnimationState.DANCING:
            sequence = self._pick_dancing_sequence()
            self._current_task = asyncio.create_task(
                self._send_sequence(sequence, new_state),
                name=f"animation-{new_state.name}",
            )
        else:
            packets = self._registry.get_packets(new_state)
            self._current_task = asyncio.create_task(
                self._send(packets, new_state),
                name=f"animation-{new_state.name}",
            )

    def _pick_dancing_sequence(self) -> list[tuple[list[bytes], float]]:
        """Randomly pick a dancing animation sequence.

        Returns a list of (packets, pre_delay) pairs where pre_delay is the
        number of seconds to wait before sending those packets.

        Choices:
          0 — grot-spin only
          1 — grot-dance only
          2 — grot-flip only
          3 — grot-spin followed by grot-flip
        """
        spin = self._registry.get_packets(AnimationState.DANCING)
        dance = self._registry.get_packets(AnimationState.DANCING_ALT)
        flip = self._registry.get_packets(AnimationState.DANCING_FLIP)
        choice = random.randint(0, 3)
        if choice == 0:
            return [(spin, 0.0)]
        elif choice == 1:
            return [(dance, 0.0)]
        elif choice == 2:
            return [(flip, 0.0)]
        else:
            return [(spin, 0.0), (flip, DANCING_SPIN_DURATION_S)]

    def _pick_talking_sequence(self) -> list[tuple[list[bytes], float]]:
        """Randomly pick a talking animation sequence.

        Returns a list of (packets, pre_delay) pairs where pre_delay is the
        number of seconds to wait before sending those packets.
        """
        talking = self._registry.get_packets(AnimationState.TALKING)
        talking_alt = self._registry.get_packets(AnimationState.TALKING_ALT)
        choice = random.randint(0, 2)
        if choice == 0:
            return [(talking, 0.0)]
        elif choice == 1:
            return [(talking_alt, 0.0)]
        else:
            return [(talking, 0.0), (talking_alt, ANIMATION_DURATION_S)]

    async def _send(self, packets: list[bytes], state: AnimationState) -> None:
        try:
            await self._device.send_packets(packets)
            logger.debug("Animation upload complete: %s", state.name)
        except asyncio.CancelledError:
            logger.debug("Animation upload cancelled: %s", state.name)
        except Exception:
            logger.exception("Animation upload failed: %s", state.name)

    async def _send_sequence(
        self,
        sequence: list[tuple[list[bytes], float]],
        state: AnimationState,
    ) -> None:
        try:
            for packets, pre_delay in sequence:
                if pre_delay > 0:
                    await asyncio.sleep(pre_delay)
                await self._device.send_packets(packets)
            logger.debug("Animation sequence complete: %s", state.name)
        except asyncio.CancelledError:
            logger.debug("Animation sequence cancelled: %s", state.name)
        except Exception:
            logger.exception("Animation sequence failed: %s", state.name)

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
