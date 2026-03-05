"""WebSocket server that exposes the Grot voice-chat pipeline to any frontend.

Wraps OpenAIChatSession, transcribe(), synthesize(), AnimationController, and
DeviceService behind a JSON-over-WebSocket API so a UI (e.g. the Tauri
walkie-talkie app) can drive the session without touching BLE or audio APIs
directly.

Protocol (all messages are JSON with a ``type`` field):

Client → Server
  { "type": "voice_audio",    "data": "<base64 WAV>" }
  { "type": "audio_done" }                                       # signals playback complete
  { "type": "command",        "text": "/animation dancing" }
  { "type": "connect_device", "address": "AA:BB:CC:DD:EE:FF" }  # optional
  { "type": "disconnect" }

Server → Client
  { "type": "ready" }
  { "type": "status",         "text": "..." }
  { "type": "transcription",  "text": "..." }
  { "type": "chat_token",     "text": "..." }
  { "type": "chat_done",      "text": "..." }
  { "type": "voice_audio",    "data": "<base64 WAV>" }
  { "type": "animation",      "state": "talking" }
  { "type": "error",          "text": "..." }
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import openai as _openai
import websockets
from websockets.asyncio.server import ServerConnection, serve

from . import protocol
from .animations import AnimationController, AnimationRegistry, AnimationState
from .chat import extract_mood, strip_mood_tag
from .chat_commands import (
    ANIMATION_NAMES,
    EXIT_COMMANDS,
    IDLE_REVERT_DELAY,
    play_sleeping,
)
from .openai_chat import OpenAIChatSession, synthesize, transcribe
from .prompts import DEFAULT_TEMPERATURE, GREETING_PROMPT
from .service import DeviceService

logger = logging.getLogger(__name__)

DEFAULT_PORT: int = 8765


class GrotWebSocketServer:
    """Single-connection WebSocket server for the Grot walkie-talkie UI.

    Only one client connection is supported at a time.  If a second client
    connects while one is active, the second connection receives an error and
    is closed immediately.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        tts_voice: str = "nova",
        animations_dir: Path = Path("grot_animations"),
        device_address: str | None = None,
        device_name_prefix: str = "IDM-",
        use_cache: bool = True,
        chunk_size: int = protocol.DEFAULT_CHUNK_SIZE,
        port: int = DEFAULT_PORT,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._tts_voice = tts_voice
        self._animations_dir = animations_dir
        self._device_address = device_address
        self._device_name_prefix = device_name_prefix
        self._use_cache = use_cache
        self._chunk_size = chunk_size
        self._port = port
        self._temperature = temperature

        # Runtime state (populated during handler lifecycle)
        self._client: ServerConnection | None = None
        self._session: OpenAIChatSession | None = None
        self._openai_client: _openai.AsyncOpenAI | None = None
        self._device: DeviceService | None = None
        self._controller: AnimationController | None = None
        self._processing: bool = False
        self._audio_done_event: asyncio.Event | None = None

    # ------------------------------------------------------------------
    # Sending helpers
    # ------------------------------------------------------------------

    async def _send(self, msg: dict[str, Any]) -> None:
        """Serialise *msg* to JSON and send to the connected client."""
        if self._client is None:
            return
        try:
            await self._client.send(json.dumps(msg))
        except Exception:
            logger.debug("Failed to send message %s", msg.get("type"), exc_info=True)

    async def _send_status(self, text: str) -> None:
        await self._send({"type": "status", "text": text})

    async def _send_error(self, text: str) -> None:
        await self._send({"type": "error", "text": text})

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def _setup(self) -> bool:
        """Preload animations and connect to the BLE device.

        Returns True on success, False if setup failed (error already sent).
        """
        await self._send_status("Loading animations...")
        registry = AnimationRegistry(self._animations_dir)
        try:
            registry.preload(chunk_size=self._chunk_size)
        except FileNotFoundError as exc:
            await self._send_error(str(exc))
            return False

        await self._send_status(
            f"Animations loaded ({registry.loaded_count} states)."
        )

        await self._send_status("Connecting to iDotMatrix device...")
        self._device = DeviceService(
            device_address=self._device_address,
            device_name_prefix=self._device_name_prefix,
            use_cache=self._use_cache,
        )
        try:
            await self._device.connect()
        except Exception as exc:
            await self._send_error(
                f"Could not connect to device: {exc}. "
                "Make sure the device is powered on and within BLE range."
            )
            return False

        address = self._device.address or "unknown"
        await self._send_status(f"Connected to {address}.")

        def _on_state_change(state: AnimationState) -> None:
            asyncio.get_event_loop().create_task(
                self._send({"type": "animation", "state": state.name.lower()})
            )

        self._controller = AnimationController(
            self._device, registry, on_state_change=_on_state_change
        )
        self._session = OpenAIChatSession(
            api_key=self._api_key,
            model=self._model,
            temperature=self._temperature,
        )
        self._openai_client = _openai.AsyncOpenAI(api_key=self._api_key)

        return True

    async def _teardown(self) -> None:
        """Graceful shutdown: sleeping animation → disconnect BLE."""
        if self._controller is not None:
            await play_sleeping(self._controller)
            await self._controller.shutdown()
        if self._device is not None:
            try:
                await self._device.disconnect()
            except Exception:
                logger.debug("Error disconnecting device", exc_info=True)
        self._device = None
        self._controller = None
        self._session = None
        self._openai_client = None

    async def _send_greeting(self) -> None:
        """Generate and stream Grot's opening greeting to the client."""
        assert self._session is not None
        assert self._controller is not None
        assert self._openai_client is not None

        # Hold the processing flag so voice_audio messages received during the
        # greeting are rejected rather than racing with the greeting pipeline.
        self._processing = True
        try:
            await self._send_greeting_inner()
        finally:
            self._processing = False

    async def _send_greeting_inner(self) -> None:
        """Inner greeting logic (runs inside _send_greeting's processing guard)."""
        assert self._session is not None
        assert self._controller is not None
        assert self._openai_client is not None

        await self._controller.transition(AnimationState.EXCITED)
        await self._send_status("Grot is waking up...")

        self._session.add_user_message(GREETING_PROMPT)
        full_response = ""
        async for chunk in self._session.stream_response():
            full_response += chunk
            await self._send({"type": "chat_token", "text": chunk})

        clean_text = strip_mood_tag(full_response)
        self._session.add_assistant_message(full_response)

        await self._send({"type": "chat_done", "text": clean_text})

        if clean_text:
            await self._send_status("Grot is preparing voice...")
            audio = await synthesize(
                clean_text,
                api_key="",
                voice=self._tts_voice,
                client=self._openai_client,
            )
            self._audio_done_event = asyncio.Event()
            await self._controller.transition(AnimationState.TALKING)
            await self._send(
                {"type": "voice_audio", "data": base64.b64encode(audio).decode()}
            )
            try:
                await asyncio.wait_for(self._audio_done_event.wait(), timeout=120.0)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for audio_done signal in greeting; proceeding anyway")

        await self._controller.transition(AnimationState.IDLE)

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    async def _handle_voice_audio(self, data: str) -> None:
        """Process a base64-encoded WAV message through the full voice pipeline."""
        if self._processing:
            await self._send_status("Still processing previous message, please wait.")
            return

        assert self._session is not None
        assert self._controller is not None
        assert self._openai_client is not None

        self._processing = True
        try:
            # Decode audio
            try:
                wav_bytes = base64.b64decode(data)
            except Exception:
                await self._send_error("Invalid audio data (base64 decoding failed).")
                return

            if not wav_bytes:
                await self._send_status("No audio captured. Please try again.")
                return

            # Transition to THINKING while we process
            await self._controller.transition(AnimationState.THINKING)
            await self._send_status("Transcribing...")

            text = await transcribe(wav_bytes, api_key="", client=self._openai_client)

            if not text:
                await self._send_status("Could not understand audio. Please try again.")
                await self._controller.transition(AnimationState.IDLE)
                return

            await self._send({"type": "transcription", "text": text})

            # Stream LLM response
            self._session.add_user_message(text)
            full_response = ""
            await self._send_status("Grot is thinking...")

            async for chunk in self._session.stream_response():
                full_response += chunk
                await self._send({"type": "chat_token", "text": chunk})

            clean_text = strip_mood_tag(full_response)
            self._session.add_assistant_message(full_response)
            await self._send({"type": "chat_done", "text": clean_text})

            # Synthesize TTS
            audio: bytes | None = None
            if clean_text:
                await self._send_status("Grot is preparing voice...")
                audio = await synthesize(
                        clean_text,
                        api_key="",
                        voice=self._tts_voice,
                        client=self._openai_client,
                    )

            # TALKING animation + send audio together; wait for client to
            # signal playback completion before advancing the animation state.
            self._audio_done_event = asyncio.Event()
            await self._controller.transition(AnimationState.TALKING)
            if audio:
                await self._send(
                    {"type": "voice_audio", "data": base64.b64encode(audio).decode()}
                )
                try:
                    await asyncio.wait_for(self._audio_done_event.wait(), timeout=120.0)
                except asyncio.TimeoutError:
                    logger.warning("Timed out waiting for audio_done signal; proceeding anyway")

            # Settle into mood. [mood:talking] means a normal conversational reply
            # — once audio has finished playing, simply revert to idle.
            mood = extract_mood(full_response)
            if mood == AnimationState.TALKING:
                mood = AnimationState.IDLE
            await self._controller.transition(mood)

            if mood != AnimationState.IDLE:
                await self._controller.await_current()
                await asyncio.sleep(IDLE_REVERT_DELAY)
                await self._controller.transition(AnimationState.IDLE)

        except Exception as exc:
            logger.exception("Error in voice pipeline")
            await self._send_error(f"Processing error: {exc}")
            if self._controller is not None:
                await self._controller.transition(AnimationState.IDLE)
        finally:
            self._processing = False

    async def _handle_command(self, text: str) -> None:
        """Handle a slash command from the client."""
        assert self._controller is not None

        raw = text.strip().lower()
        cmd = raw if raw.startswith("/") else f"/{raw}"

        if cmd in EXIT_COMMANDS:
            await self._send_status("Goodbye!")
            if self._client is not None:
                await self._client.close()
            return

        if cmd == "/help":
            help_lines = [
                "/exit — Exit the session",
                "/help — Show this help",
                f"/animation <name> — Play an animation ({', '.join(ANIMATION_NAMES)})",
            ]
            await self._send_status("Commands: " + "  |  ".join(help_lines))
            return

        if cmd.startswith("/animation"):
            parts = cmd.split(maxsplit=1)
            if len(parts) < 2 or parts[1] not in ANIMATION_NAMES:
                names = ", ".join(ANIMATION_NAMES)
                await self._send_status(
                    f"Usage: /animation <name>  ({names})"
                )
                return
            state = ANIMATION_NAMES[parts[1]]
            await self._send_status(f"Playing animation: {state.name.lower()}")
            await self._controller.transition(state)
            await self._controller.await_current()
            await asyncio.sleep(IDLE_REVERT_DELAY)
            await self._controller.transition(AnimationState.IDLE)
            return

        await self._send_status(
            f"Unknown command: {cmd}  (type /help for available commands)"
        )

    # ------------------------------------------------------------------
    # WebSocket handler
    # ------------------------------------------------------------------

    async def _handler(self, websocket: ServerConnection) -> None:
        """Handle a single client connection."""
        if self._client is not None:
            # Only one active connection is supported
            await websocket.send(
                json.dumps(
                    {
                        "type": "error",
                        "text": "Another client is already connected.",
                    }
                )
            )
            await websocket.close()
            return

        self._client = websocket
        logger.info("Client connected: %s", websocket.remote_address)

        try:
            ok = await self._setup()
            if not ok:
                return

            await self._send({"type": "ready"})
            # Run greeting as a background task so the message loop below starts
            # immediately — this is required for the audio_done signal sent by
            # the client to be received while the greeting is still in progress.
            asyncio.create_task(self._send_greeting())

            async for raw_msg in websocket:
                try:
                    msg = json.loads(raw_msg)
                except json.JSONDecodeError:
                    await self._send_error("Invalid JSON message.")
                    continue

                msg_type = msg.get("type")

                if msg_type == "voice_audio":
                    asyncio.create_task(
                        self._handle_voice_audio(msg.get("data", ""))
                    )

                elif msg_type == "command":
                    await self._handle_command(msg.get("text", ""))

                elif msg_type == "audio_done":
                    if self._audio_done_event is not None:
                        self._audio_done_event.set()

                elif msg_type == "connect_device":
                    # Device is already connected at startup; ignore late re-connect requests
                    await self._send_status(
                        f"Already connected to {self._device.address or 'device'}."
                        if self._device
                        else "Not connected."
                    )

                elif msg_type == "disconnect":
                    await self._send_status("Disconnecting...")
                    break

                else:
                    await self._send_error(f"Unknown message type: {msg_type!r}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected normally")
        except Exception:
            logger.exception("Unexpected error in WebSocket handler")
        finally:
            # Clear _client immediately so reconnecting clients are not rejected
            # while the (potentially slow) BLE teardown is still in progress.
            self._client = None
            await self._teardown()
            logger.info("Handler cleanup complete")

    # ------------------------------------------------------------------
    # Server entry point
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket server and block until interrupted."""
        logger.info("WebSocket server listening on ws://localhost:%d", self._port)
        print(f"WebSocket server listening on ws://localhost:{self._port}", flush=True)

        async with serve(self._handler, "localhost", self._port):
            try:
                await asyncio.get_running_loop().create_future()  # run forever
            except (KeyboardInterrupt, asyncio.CancelledError):
                logger.info("Server shutting down")
