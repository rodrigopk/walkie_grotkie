from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idotmatrix_upload.animations import (
    ANIMATION_MAP,
    ANIMATION_DURATION_S,
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


# ---------------------------------------------------------------------------
# Talking sequence
# ---------------------------------------------------------------------------


class TestTalkingSequence:
    @pytest.mark.asyncio
    async def test_talking_sends_at_least_one_packet_set(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        await controller.transition(AnimationState.TALKING)
        await asyncio.sleep(0.05)

        assert device.send_packets.call_count >= 1
        assert controller.current_state == AnimationState.TALKING

    @pytest.mark.asyncio
    async def test_talking_choice_0_sends_talking_only(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        with patch("idotmatrix_upload.animations.random.randint", return_value=0):
            await controller.transition(AnimationState.TALKING)
            await asyncio.sleep(0.05)

        assert device.send_packets.call_count == 1
        assert device.send_packets.call_args[0][0] == registry.get_packets(AnimationState.TALKING)

    @pytest.mark.asyncio
    async def test_talking_choice_1_sends_talking_alt_only(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        with patch("idotmatrix_upload.animations.random.randint", return_value=1):
            await controller.transition(AnimationState.TALKING)
            await asyncio.sleep(0.05)

        assert device.send_packets.call_count == 1
        assert device.send_packets.call_args[0][0] == registry.get_packets(AnimationState.TALKING_ALT)

    @pytest.mark.asyncio
    async def test_talking_choice_2_sends_both_with_delay(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        # Patch ANIMATION_DURATION_S to 0 so the real asyncio.sleep returns
        # immediately, letting the background task finish quickly.
        with (
            patch("idotmatrix_upload.animations.random.randint", return_value=2),
            patch("idotmatrix_upload.animations.ANIMATION_DURATION_S", 0.0),
        ):
            await controller.transition(AnimationState.TALKING)
            await asyncio.sleep(0.1)

        assert device.send_packets.call_count == 2
        first_call_packets = device.send_packets.call_args_list[0][0][0]
        second_call_packets = device.send_packets.call_args_list[1][0][0]
        assert first_call_packets == registry.get_packets(AnimationState.TALKING)
        assert second_call_packets == registry.get_packets(AnimationState.TALKING_ALT)

    @pytest.mark.asyncio
    async def test_pick_talking_sequence_uses_animation_duration(self, tmp_path: Path):
        """Verify that the two-animation sequence uses ANIMATION_DURATION_S as pre-delay."""
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        controller = AnimationController(device, registry)
        with patch("idotmatrix_upload.animations.random.randint", return_value=2):
            sequence = controller._pick_talking_sequence()

        assert len(sequence) == 2
        _, first_delay = sequence[0]
        _, second_delay = sequence[1]
        assert first_delay == 0.0
        assert second_delay == ANIMATION_DURATION_S

    @pytest.mark.asyncio
    async def test_talking_sequence_is_cancellable(self, tmp_path: Path):
        anim_dir = _create_animation_dir(tmp_path)
        registry = AnimationRegistry(anim_dir)
        registry.preload()
        device = _mock_device()

        stall = asyncio.Event()
        device.send_packets = AsyncMock(side_effect=lambda *a, **kw: stall.wait())

        controller = AnimationController(device, registry)
        with patch("idotmatrix_upload.animations.random.randint", return_value=2):
            await controller.transition(AnimationState.TALKING)

        await controller.transition(AnimationState.IDLE)
        assert controller.current_state == AnimationState.IDLE

        stall.set()
        await controller.shutdown()
