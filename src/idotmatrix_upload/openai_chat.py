"""OpenAI-backed chat session, speech-to-text, and text-to-speech for Grot.

Three responsibilities, one SDK:
  - OpenAIChatSession: streaming GPT-4o chat completions (drop-in for ChatSession)
  - transcribe():      WAV bytes -> text via Whisper (gpt-4o-transcribe)
  - synthesize():      text -> WAV bytes via TTS (gpt-4o-mini-tts)

The SYSTEM_PROMPT and [mood:...] tag convention are imported from chat.py so
both text and voice chat share the same Grot personality and animation logic.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import openai

from .prompts import DEFAULT_TEMPERATURE, GROT_VOICE_INSTRUCTIONS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OpenAIChatSession:
    """Streaming GPT-4o chat session that maintains conversation history.

    API-compatible with the Anthropic ChatSession in chat.py:
    same add_user_message / add_assistant_message / stream_response interface.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 512,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)
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

    async def stream_response(self) -> AsyncGenerator[str, None]:
        """Yield text chunks from the streaming GPT-4o API.

        The caller is responsible for collecting the full text and calling
        add_assistant_message() afterwards.
        """
        stream = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            stream=True,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *self._messages,
            ],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


async def transcribe(audio_bytes: bytes, api_key: str) -> str:
    """Convert WAV audio bytes to text using OpenAI's Whisper model.

    Args:
        audio_bytes: WAV-formatted audio captured from the microphone.
        api_key: OpenAI API key.

    Returns:
        Transcribed text, stripped of leading/trailing whitespace.
        Returns an empty string if the recording was silent or too short.
    """
    client = openai.AsyncOpenAI(api_key=api_key)

    # The API expects a file-like object with a name hint for the format.
    import io
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "recording.wav"

    try:
        result = await client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file,
            response_format="text",
        )
    except openai.BadRequestError as exc:
        logger.warning("Transcription rejected (likely silent): %s", exc)
        return ""

    text = str(result).strip()
    logger.debug("Transcribed: %r", text)
    return text


async def synthesize(
    text: str,
    api_key: str,
    voice: str = "nova",
    voice_instructions: str = GROT_VOICE_INSTRUCTIONS,
) -> bytes:
    """Convert text to spoken audio using OpenAI's TTS model.

    Args:
        text: The text to speak (mood tags should be stripped before calling).
        api_key: OpenAI API key.
        voice: One of the OpenAI TTS voice names (alloy, ash, coral, echo,
               fable, nova, onyx, sage, shimmer, verse).
        voice_instructions: Personality/style prompt for gpt-4o-mini-tts.

    Returns:
        WAV audio bytes ready to be played back via voice.play_audio().
    """
    client = openai.AsyncOpenAI(api_key=api_key)

    response = await client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,  # type: ignore[arg-type]
        input=text,
        response_format="wav",
        extra_body={"instructions": voice_instructions},
    )

    audio_bytes = response.read()
    logger.debug("Synthesized %d bytes of audio for %d chars of text", len(audio_bytes), len(text))
    return audio_bytes
