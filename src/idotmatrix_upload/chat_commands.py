"""Shared slash-command helpers and state-machine utilities.

This module owns the reusable pieces used by both the text chat loop (chat.py)
and the voice chat loop (voice_chat.py).  Keeping them here avoids importing
private symbols across modules and makes ownership boundaries clear.

Public API
----------
EXIT_COMMANDS          — frozenset of slash commands that end the session
SLASH_COMMANDS         — ordered dict of commands with descriptions
ANIMATION_NAMES        — mapping of animation name strings to AnimationState
IDLE_REVERT_DELAY      — seconds to hold an animation before reverting to idle
state_label()          — turn an AnimationState into a human-readable string
print_help()           — render the help table to a Rich Console
play_sleeping()        — transition to SLEEPING and await completion (exit path)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from rich.console import Console
from rich.panel import Panel

from .animations import AnimationController, AnimationState

logger = logging.getLogger(__name__)

# How long (seconds) to hold a non-idle animation before reverting to IDLE.
IDLE_REVERT_DELAY: float = 2.0

# Maps the string names used in [mood:...] tags and /animation commands to states.
ANIMATION_NAMES: dict[str, AnimationState] = {
    "idle":      AnimationState.IDLE,
    "thinking":  AnimationState.THINKING,
    "talking":   AnimationState.TALKING,
    "excited":   AnimationState.EXCITED,
    "dancing":   AnimationState.DANCING,
    "sleeping":  AnimationState.SLEEPING,
    "surprised": AnimationState.SURPRISED,
}

EXIT_COMMANDS: frozenset[str] = frozenset({"/exit"})

SLASH_COMMANDS: dict[str, str] = {
    "/exit":       "Exit the chat",
    "/help":       "Show this help message",
    "/animation":  f"Preview an animation ({', '.join(ANIMATION_NAMES)})",
}


def state_label(state: AnimationState | None) -> str:
    """Return a human-readable label for an animation state (e.g. ``"talking"``)."""
    if state is None:
        return "none"
    return state.name.lower().replace("_", " ")


def print_help(console: Console, extra: dict[str, str] | None = None) -> None:
    """Render the slash-command help table to *console*.

    Args:
        console: Rich Console to print to.
        extra: Additional command -> description entries to append.
    """
    from rich.table import Table

    commands = {**SLASH_COMMANDS, **(extra or {})}
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="dim")
    for cmd, description in commands.items():
        table.add_row(cmd, description)
    console.print(Panel(table, title="Commands", border_style="dim"))


async def play_sleeping(controller: AnimationController) -> None:
    """Transition to SLEEPING and wait for the animation to finish.

    Used as the graceful exit animation before disconnecting.  Failures are
    suppressed so they never interrupt shutdown.
    """
    try:
        await controller.transition(AnimationState.SLEEPING)
        await controller.await_current()
    except Exception:
        logger.debug("Sleeping animation skipped on exit", exc_info=True)


async def handle_animation_command(
    raw: str,
    console: Console,
    controller: AnimationController,
) -> None:
    """Handle the ``/animation <name>`` slash command.

    Transitions to the requested animation, holds it briefly, then reverts to
    IDLE.  Prints usage guidance if the animation name is missing or unknown.

    Args:
        raw: The full slash-command string (e.g. ``"/animation dancing"``).
        console: Rich Console for output.
        controller: Active AnimationController.
    """
    parts = raw.split(maxsplit=1)
    if len(parts) < 2 or parts[1] not in ANIMATION_NAMES:
        names = ", ".join(ANIMATION_NAMES)
        console.print(f"[yellow]Usage:[/yellow] /animation <name>  ({names})")
        return
    state = ANIMATION_NAMES[parts[1]]
    console.print(f"[dim]Playing animation: {state.name.lower()}[/dim]")
    await controller.transition(state)
    await controller.await_current()
    await asyncio.sleep(IDLE_REVERT_DELAY)
    await controller.transition(AnimationState.IDLE)
