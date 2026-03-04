"""Voice chat session with push-to-talk input and TTS output.

Wires together:
  - PushToTalkRecorder  (voice.py)   — microphone capture
  - transcribe()        (openai_chat.py) — Whisper STT
  - OpenAIChatSession   (openai_chat.py) — GPT-4o LLM
  - synthesize()        (openai_chat.py) — TTS
  - play_audio()        (voice.py)   — speaker playback
  - AnimationController (animations.py) — iDotMatrix BLE animations

The animation state machine mirrors the text chat states:
  THINKING  -> while listening (spacebar held) + transcribing + waiting for LLM
  TALKING   -> synchronized with TTS audio playback
  <mood>    -> brief mood expression after speaking
  IDLE      -> back to rest
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from . import protocol
from .animations import AnimationController, AnimationRegistry, AnimationState
from .chat import (
    _EXIT_COMMANDS,             # noqa: PLC2701
    _IDLE_REVERT_DELAY,         # noqa: PLC2701
    _play_sleeping,             # noqa: PLC2701
    _print_help,                # noqa: PLC2701
    _state_label,               # noqa: PLC2701
    extract_mood,
    handle_animation_command,
    strip_mood_tag,
)
from .openai_chat import TTS_VOICES, OpenAIChatSession, synthesize, transcribe
from .prompts import DEFAULT_TEMPERATURE, GREETING_PROMPT
from .service import DeviceService
from .voice import (
    PushToTalkRecorder,
    disable_terminal_echo,
    flush_stdin,
    play_audio,
    restore_terminal,
)

logger = logging.getLogger(__name__)


async def run_voice_chat(
    api_key: str,
    model: str,
    animations_dir: Path,
    tts_voice: str = "nova",
    device_address: str | None = None,
    device_name_prefix: str = "IDM-",
    use_cache: bool = True,
    chunk_size: int = protocol.DEFAULT_CHUNK_SIZE,
    temperature: float = DEFAULT_TEMPERATURE,
    animation_debug: bool = False,
) -> None:
    """Main entry point for voice chat.

    Args:
        api_key: OpenAI API key (used for STT, LLM, and TTS).
        model: GPT model name (e.g. 'gpt-4o').
        animations_dir: Path to the grot_animations directory.
        tts_voice: OpenAI TTS voice name.
        device_address: Optional explicit BLE address (skips scanning).
        device_name_prefix: BLE device name prefix for scanning.
        use_cache: Whether to use the BLE address cache.
        chunk_size: Protocol chunk size for BLE uploads.
        temperature: LLM sampling temperature.
        animation_debug: When True, print every animation state transition.
    """
    console = Console()

    console.print(
        Panel(
            "[bold]Grot Voice Chat[/bold] — iDotMatrix + OpenAI",
            subtitle="Hold [bold]SPACE[/bold] to speak  •  Press [bold]/[/bold] for commands  •  Ctrl-C to quit",
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
    console.print("[green]Animations loaded[/green]")

    # -- Connect to device --
    console.print("[dim]Connecting to iDotMatrix device...[/dim]")
    async with DeviceService(
        device_address=device_address,
        device_name_prefix=device_name_prefix,
        use_cache=use_cache,
    ) as device:
        address = device.address or "unknown"
        console.print(f"[green]Connected to {address}[/green]\n")

        def _on_state_change(state: AnimationState) -> None:
            if animation_debug:
                console.print(f"  [dim]animation: {_state_label(state)}[/dim]")

        controller = AnimationController(
            device, registry,
            on_state_change=_on_state_change if animation_debug else None,
        )
        session = OpenAIChatSession(api_key=api_key, model=model, temperature=temperature)
        recorder = PushToTalkRecorder()
        recorder.start_listener()

        try:
            await controller.transition(AnimationState.EXCITED)
            await _send_greeting(console, session, controller, api_key, tts_voice)
            await asyncio.sleep(_IDLE_REVERT_DELAY)
            await controller.transition(AnimationState.IDLE)

            await _voice_loop(console, session, controller, recorder, api_key, tts_voice)
        finally:
            recorder.stop_listener()
            await _play_sleeping(controller)
            await controller.shutdown()

    console.print("\n[dim]Disconnected. Goodbye![/dim]")


async def _send_greeting(
    console: Console,
    session: OpenAIChatSession,
    controller: AnimationController,
    api_key: str,
    tts_voice: str,
) -> None:
    """Generate, display, and speak Grot's opening greeting."""
    session.add_user_message(GREETING_PROMPT)
    full_response = ""

    with Live(
        Spinner("dots", text="Grot is waking up...", style="yellow"),
        console=console,
        refresh_per_second=12,
    ) as live:
        async for chunk in session.stream_response():
            full_response += chunk
        clean_text = strip_mood_tag(full_response)
        if clean_text:
            live.update(Spinner("dots", text="Grot is preparing...", style="yellow"))
            audio = await synthesize(clean_text, api_key, voice=tts_voice)
        else:
            audio = None

    session.add_assistant_message(full_response)

    if clean_text:
        console.print(
            Panel(
                Markdown(clean_text),
                title="[bold cyan]Grot[/bold cyan]",
                border_style="cyan",
            )
        )
    if audio:
        await play_audio(audio)


async def _voice_loop(
    console: Console,
    session: OpenAIChatSession,
    controller: AnimationController,
    recorder: PushToTalkRecorder,
    api_key: str,
    tts_voice: str,
) -> None:
    """Main push-to-talk loop."""
    while True:
        console.print(
            "\n[dim]Hold [bold]SPACE[/bold] to speak  •  Press [bold]/[/bold] for commands[/dim]"
        )

        # Disable echo so the spacebar and '/' keystrokes don't appear in the terminal.
        old_term = disable_terminal_echo()

        try:
            result = await _wait_for_input(console, controller, recorder)
        except KeyboardInterrupt:
            restore_terminal(old_term)
            flush_stdin()
            break

        restore_terminal(old_term)
        flush_stdin()

        # -- Command mode: '/' was pressed --
        if result is None:
            user_input = await asyncio.to_thread(
                console.input, "[bold green]command> [/bold green]"
            )
            raw = user_input.strip().lower()
            cmd = raw if raw.startswith("/") else f"/{raw}"
            if cmd in _EXIT_COMMANDS or cmd == "/":
                break
            if cmd == "/help":
                _print_help(
                    console,
                    extra={
                        "/animation": "Preview an animation (idle, thinking, talking, excited, dancing)",
                        "/voice":     f"Switch TTS voice ({', '.join(sorted(TTS_VOICES))})",
                    },
                )
            elif cmd.startswith("/animation"):
                await handle_animation_command(cmd, console, controller)
            elif cmd.startswith("/voice"):
                parts = cmd.split(maxsplit=1)
                if len(parts) < 2 or parts[1] not in TTS_VOICES:
                    console.print(
                        f"[yellow]Usage:[/yellow] /voice <name>  "
                        f"({', '.join(sorted(TTS_VOICES))})"
                    )
                else:
                    tts_voice = parts[1]
                    console.print(f"[green]Voice set to:[/green] {tts_voice}")
            else:
                console.print(
                    f"[yellow]Unknown command:[/yellow] {cmd}  "
                    f"(type [bold]/help[/bold] for available commands)"
                )
            continue

        wav_bytes = result

        if not wav_bytes:
            console.print("[yellow]No audio captured. Try again.[/yellow]")
            continue

        # -- Transcribe (THINKING animation already active from spacebar press) --
        with Live(
            Spinner("dots", text="Transcribing...", style="yellow"),
            console=console,
            refresh_per_second=12,
        ):
            text = await transcribe(wav_bytes, api_key)

        if not text:
            console.print("[yellow]Could not understand audio. Try again.[/yellow]")
            await controller.transition(AnimationState.IDLE)
            continue

        console.print(
            Panel(
                text,
                title="[bold green]You (voice)[/bold green]",
                border_style="green",
            )
        )

        # -- LLM response: collect silently, then synthesize TTS --
        session.add_user_message(text)
        full_response = ""

        with Live(
            Spinner("dots", text="Grot is thinking...", style="yellow"),
            console=console,
            refresh_per_second=12,
        ) as live:
            async for chunk in session.stream_response():
                full_response += chunk
            clean_text = strip_mood_tag(full_response)
            if clean_text:
                live.update(Spinner("dots", text="Grot is preparing...", style="yellow"))
                audio = await synthesize(clean_text, api_key, voice=tts_voice)
            else:
                audio = None

        session.add_assistant_message(full_response)

        # -- Synchronized reveal: TALKING animation + text + audio together --
        await controller.transition(AnimationState.TALKING)
        if clean_text:
            console.print(
                Panel(
                    Markdown(clean_text),
                    title="[bold cyan]Grot[/bold cyan]",
                    border_style="cyan",
                )
            )
        if audio:
            await play_audio(audio)

        # -- Settle into mood animation immediately after audio ends --
        mood = extract_mood(full_response)
        await controller.transition(mood)

        if mood != AnimationState.IDLE:
            await controller.await_current()
            await asyncio.sleep(_IDLE_REVERT_DELAY)
            await controller.transition(AnimationState.IDLE)

        console.print()


async def _wait_for_input(
    console: Console,
    controller: AnimationController,
    recorder: PushToTalkRecorder,
) -> bytes | None:
    """Wait for spacebar (record) or '/' (command mode).

    Returns WAV bytes on spacebar press-and-release, or None on '/' press.
    Transitions to THINKING immediately when spacebar is pressed.
    """

    def _on_listening() -> None:
        console.print("[cyan]Recording... (release SPACE when done)[/cyan]")
        asyncio.get_event_loop().create_task(
            controller.transition(AnimationState.THINKING)
        )

    def _on_stop() -> None:
        console.print("[dim]Processing...[/dim]")

    return await recorder.wait_for_input(
        on_listening=_on_listening,
        on_recording_stop=_on_stop,
    )
