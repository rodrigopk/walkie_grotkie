"""Interactive chat session with LLM-driven iDotMatrix animations.

Connects to an Anthropic model for conversation while driving grot
animations on the LED matrix based on conversation state and mood.
Uses Rich for a styled terminal UI with streaming responses.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

import anthropic
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from .animations import AnimationController, AnimationRegistry, AnimationState
from .prompts import DEFAULT_TEMPERATURE, GREETING_PROMPT, SYSTEM_PROMPT
from .service import DeviceService

logger = logging.getLogger(__name__)

_MOOD_PATTERN = re.compile(r"\[mood:(\w+)\]")

_MOOD_MAP: dict[str, AnimationState] = {
    "idle": AnimationState.IDLE,
    "talking": AnimationState.TALKING,
    "excited": AnimationState.EXCITED,
    "thinking": AnimationState.THINKING,
    "dancing": AnimationState.DANCING,
}


def extract_mood(response: str) -> AnimationState:
    """Parse a [mood:...] tag from the response text.

    Returns the mapped AnimationState, defaulting to IDLE if no valid tag found.
    """
    match = _MOOD_PATTERN.search(response)
    if match and match.group(1) in _MOOD_MAP:
        return _MOOD_MAP[match.group(1)]
    return AnimationState.IDLE


def strip_mood_tag(response: str) -> str:
    """Remove the [mood:...] tag from the response for display."""
    return _MOOD_PATTERN.sub("", response).rstrip()


class ChatSession:
    """Wraps the Anthropic streaming API and maintains conversation history."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 512,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._messages: list[dict[str, str]] = []

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    async def stream_response(self):
        """Yield text chunks from the streaming API.

        The caller is responsible for collecting the full text and calling
        add_assistant_message() afterwards.
        """
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=SYSTEM_PROMPT,
            messages=self._messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


_SLASH_COMMANDS = {
    "/quit": "Exit the chat",
    "/exit": "Exit the chat",
    "/bye":  "Exit the chat",
    "/help": "Show this help message",
}

_EXIT_COMMANDS = frozenset({"/quit", "/exit", "/bye"})


def _print_help(console: Console) -> None:
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column(style="dim")
    for cmd, description in _SLASH_COMMANDS.items():
        table.add_row(cmd, description)
    console.print(Panel(table, title="Commands", border_style="dim"))


def _state_label(state: AnimationState | None) -> str:
    if state is None:
        return "none"
    return state.name.lower().replace("_", " ")


_IDLE_REVERT_DELAY: float = 2.0


async def run_chat(
    api_key: str,
    model: str,
    animations_dir: Path,
    device_address: str | None = None,
    device_name_prefix: str = "IDM-",
    use_cache: bool = True,
    chunk_size: int = 4096,
    temperature: float = DEFAULT_TEMPERATURE,
) -> None:
    """Main chat loop: Rich UI + LLM streaming + iDotMatrix animations."""
    console = Console()

    # -- Startup banner --
    console.print(
        Panel(
            "[bold]Grot Chat[/bold] — iDotMatrix + Claude",
            subtitle="Type [bold]/help[/bold] for commands  •  Ctrl-C to quit",
            style="cyan",
        )
    )

    # -- Preload animations --
    console.print("[dim]Loading animations...[/dim]")
    registry = AnimationRegistry(animations_dir)
    try:
        registry.preload(chunk_size=chunk_size)
    except FileNotFoundError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return
    console.print(
        f"[green]Loaded {registry.loaded_count} animations[/green]"
    )

    # -- Connect to device --
    console.print("[dim]Connecting to iDotMatrix device...[/dim]")
    async with DeviceService(
        device_address=device_address,
        device_name_prefix=device_name_prefix,
        use_cache=use_cache,
    ) as device:
        address = device.address or "unknown"
        console.print(f"[green]Connected to {address}[/green]\n")

        animation_status = Text("idle", style="cyan")

        def _on_state_change(state: AnimationState) -> None:
            animation_status.plain = _state_label(state)

        controller = AnimationController(
            device, registry, on_state_change=_on_state_change
        )
        session = ChatSession(api_key=api_key, model=model, temperature=temperature)

        await controller.transition(AnimationState.EXCITED)
        await _send_greeting(console, session, controller)
        await asyncio.sleep(_IDLE_REVERT_DELAY)
        await controller.transition(AnimationState.IDLE)

        try:
            await _chat_loop(console, session, controller, animation_status)
        finally:
            await controller.shutdown()

    console.print("\n[dim]Disconnected. Goodbye![/dim]")


async def _send_greeting(
    console: Console,
    session: ChatSession,
    controller: AnimationController,
) -> None:
    """Stream a Claude-generated greeting and render it as Grot's opening message."""
    session.add_user_message(GREETING_PROMPT)
    full_response = ""

    with Live(
        Spinner("dots", text="Grot is waking up...", style="yellow"),
        console=console,
        refresh_per_second=12,
    ) as live:
        async for chunk in session.stream_response():
            full_response += chunk
            display_text = strip_mood_tag(full_response)
            live.update(
                Panel(
                    Markdown(display_text),
                    title="[bold cyan]Grot[/bold cyan]",
                    border_style="cyan",
                )
            )

    session.add_assistant_message(full_response)


async def _chat_loop(
    console: Console,
    session: ChatSession,
    controller: AnimationController,
    animation_status: Text,
) -> None:
    """Read-eval-print loop with Rich rendering."""
    while True:
        try:
            user_input = await asyncio.to_thread(
                console.input, "[bold green]You:[/bold green] "
            )
        except (EOFError, KeyboardInterrupt):
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in _EXIT_COMMANDS:
                break
            if cmd == "/help":
                _print_help(console)
            else:
                console.print(
                    f"[yellow]Unknown command:[/yellow] {user_input}  "
                    f"(type [bold]/help[/bold] for available commands)"
                )
            continue

        session.add_user_message(user_input)
        await controller.transition(AnimationState.THINKING)

        full_response = ""
        first_chunk = True

        with Live(
            Spinner("dots", text="Grot is thinking...", style="yellow"),
            console=console,
            refresh_per_second=12,
        ) as live:
            async for chunk in session.stream_response():
                full_response += chunk
                if first_chunk:
                    # Switch to TALKING as soon as the first token arrives
                    await controller.transition(AnimationState.TALKING)
                    first_chunk = False
                display_text = strip_mood_tag(full_response)
                live.update(
                    Panel(
                        Markdown(display_text),
                        title="[bold cyan]Grot[/bold cyan]",
                        border_style="cyan",
                    )
                )

        session.add_assistant_message(full_response)

        # Hold the TALKING animation for a moment, then settle into the mood
        await asyncio.sleep(_IDLE_REVERT_DELAY)
        mood = extract_mood(full_response)
        await controller.transition(mood)
        console.print(f"  [dim]animation: {_state_label(mood)}[/dim]")

        if mood != AnimationState.IDLE:
            await asyncio.sleep(_IDLE_REVERT_DELAY)
            await controller.transition(AnimationState.IDLE)

        console.print()
