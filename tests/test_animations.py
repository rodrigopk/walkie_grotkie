from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from idotmatrix_upload.animations import (
    ANIMATION_MAP,
    AnimationController,
    AnimationRegistry,
    AnimationState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_gif() -> bytes:
    """Minimal bytes that look like a GIF for protocol.build_packets."""
    return b"GIF89a" + b"\x00" * 100


def _create_animation_dir(tmp_path: Path) -> Path:
    """Create a directory structure matching ANIMATION_MAP with fake GIFs."""
    for rel_path in ANIMATION_MAP.values():
        gif_path = tmp_path / rel_path
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        gif_path.write_bytes(_make_fake_gif())
    return tmp_path


def _mock_device() -> MagicMock:
    device = MagicMock()
    device.send_packets = AsyncMock()
    return device


# ---------------------------------------------------------------------------
# AnimationRegistry
# ---------------------------------------------------------------------------


class TestAnimationRegistry:
    def test_preload_all_animations(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()

        unique_states = set(ANIMATION_MAP.keys())
        assert registry.loaded_count == len(unique_states)

        for state in unique_states:
            packets = registry.get_packets(state)
            assert len(packets) >= 1
            assert all(isinstance(p, bytes) for p in packets)

    def test_preload_missing_gif_raises(self, tmp_path: Path):
        registry = AnimationRegistry(tmp_path)
        with pytest.raises(FileNotFoundError, match="Animation GIF not found"):
            registry.preload()

    def test_get_packets_before_preload_raises(self, tmp_path: Path):
        registry = AnimationRegistry(tmp_path)
        with pytest.raises(KeyError):
            registry.get_packets(AnimationState.IDLE)

    def test_preload_with_custom_chunk_size(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload(chunk_size=32)

        packets = registry.get_packets(AnimationState.IDLE)
        assert len(packets) >= 1


# ---------------------------------------------------------------------------
# AnimationController
# ---------------------------------------------------------------------------


class TestAnimationController:
    @pytest.mark.asyncio
    async def test_transition_sends_packets(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        await controller.transition(AnimationState.TALKING)

        await asyncio.sleep(0.05)
        device.send_packets.assert_called_once()
        assert controller.current_state == AnimationState.TALKING

    @pytest.mark.asyncio
    async def test_transition_same_state_is_noop(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        await controller.transition(AnimationState.IDLE)
        await asyncio.sleep(0.05)

        device.send_packets.reset_mock()
        await controller.transition(AnimationState.IDLE)
        await asyncio.sleep(0.05)

        device.send_packets.assert_not_called()

    @pytest.mark.asyncio
    async def test_rapid_transitions_cancel_previous(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        stall = asyncio.Event()

        async def slow_send(packets, **kwargs):
            await stall.wait()

        device.send_packets = AsyncMock(side_effect=slow_send)

        controller = AnimationController(device, registry)
        await controller.transition(AnimationState.THINKING)

        await controller.transition(AnimationState.TALKING)

        assert controller.current_state == AnimationState.TALKING

        stall.set()
        await controller.shutdown()

    @pytest.mark.asyncio
    async def test_state_change_callback(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()
        states_received: list[AnimationState] = []

        controller = AnimationController(
            device, registry, on_state_change=states_received.append
        )
        await controller.transition(AnimationState.THINKING)
        await controller.transition(AnimationState.EXCITED)
        await asyncio.sleep(0.05)

        assert states_received == [AnimationState.THINKING, AnimationState.EXCITED]

    @pytest.mark.asyncio
    async def test_shutdown_cancels_inflight(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        stall = asyncio.Event()
        device.send_packets = AsyncMock(
            side_effect=lambda *a, **kw: stall.wait()
        )

        controller = AnimationController(device, registry)
        await controller.transition(AnimationState.DANCING)

        await controller.shutdown()
