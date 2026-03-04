"""Voice chat session with push-to-talk input and TTS output.

Wires together:
  - PushToTalkRecorder  (voice.py)   — microphone capture
  - transcribe()        (openai_chat.py) — Whisper STT
  - OpenAIChatSession   (openai_chat.py) — GPT-4o LLM
  - synthesize()        (openai_chat.py) — TTS
  - play_audio()        (voice.py)   — speaker playback
  - AnimationController (animations.py) — iDotMatrix BLE animations

The animation state machine mirrors the text chat states:
  IDLE_ALT  -> while listening (spacebar held)
  THINKING  -> while transcribing + waiting for first LLM token
  TALKING   -> while Grot's response streams in and during TTS playback
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
    _GREETING_PROMPT,           # noqa: PLC2701
    _IDLE_REVERT_DELAY,         # noqa: PLC2701
    _state_label,               # noqa: PLC2701
    extract_mood,
    strip_mood_tag,
)
from .openai_chat import OpenAIChatSession, synthesize, transcribe
from .service import DeviceService
from .voice import PushToTalkRecorder, play_audio

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
    """
    console = Console()

    console.print(
        Panel(
            "[bold]Grot Voice Chat[/bold] — iDotMatrix + OpenAI",
            subtitle="Hold [bold]SPACE[/bold] to speak  •  Ctrl-C to quit",
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
    console.print(f"[green]Loaded {registry.loaded_count} animations[/green]")

    # -- Connect to device --
    console.print("[dim]Connecting to iDotMatrix device...[/dim]")
    async with DeviceService(
        device_address=device_address,
        device_name_prefix=device_name_prefix,
        use_cache=use_cache,
    ) as device:
        address = device.address or "unknown"
        console.print(f"[green]Connected to {address}[/green]\n")

        controller = AnimationController(device, registry)
        session = OpenAIChatSession(api_key=api_key, model=model)
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
    session.add_user_message(_GREETING_PROMPT)
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

    clean_text = strip_mood_tag(full_response)
    if clean_text:
        audio = await synthesize(clean_text, api_key, voice=tts_voice)
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
            "\n[dim]Hold [bold]SPACE[/bold] to speak, release to send...[/dim]"
        )

        # -- Wait for user to press and release spacebar --
        try:
            wav_bytes = await _record_turn(console, controller, recorder)
        except KeyboardInterrupt:
            break

        if not wav_bytes:
            console.print("[yellow]No audio captured. Try again.[/yellow]")
            continue

        # -- Transcribe --
        await controller.transition(AnimationState.THINKING)
        with Live(
            Spinner("dots", text="Transcribing...", style="yellow"),
            console=console,
            refresh_per_second=12,
        ) as live:
            text = await transcribe(wav_bytes, api_key)
            live.update(Spinner("dots", text="Transcribing... done", style="green"))

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

        # -- LLM response --
        session.add_user_message(text)
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

        # -- TTS playback concurrent with mood animation --
        clean_text = strip_mood_tag(full_response)
        if clean_text:
            audio = await synthesize(clean_text, api_key, voice=tts_voice)
            # Play audio while the TALKING animation continues
            await play_audio(audio)

        # -- Settle into mood animation --
        await asyncio.sleep(_IDLE_REVERT_DELAY)
        mood = extract_mood(full_response)
        await controller.transition(mood)
        console.print(f"  [dim]animation: {_state_label(mood)}[/dim]")

        if mood != AnimationState.IDLE:
            await asyncio.sleep(_IDLE_REVERT_DELAY)
            await controller.transition(AnimationState.IDLE)

        console.print()


async def _record_turn(
    console: Console,
    controller: AnimationController,
    recorder: PushToTalkRecorder,
) -> bytes:
    """Wait for spacebar hold, record, return WAV bytes."""

    def _on_listening() -> None:
        console.print("[cyan]Recording... (release SPACE when done)[/cyan]")
        asyncio.get_event_loop().create_task(
            controller.transition(AnimationState.IDLE_ALT)
        )

    def _on_stop() -> None:
        console.print("[dim]Processing...[/dim]")

    return await recorder.wait_and_record(
        on_listening=_on_listening,
        on_recording_stop=_on_stop,
    )
