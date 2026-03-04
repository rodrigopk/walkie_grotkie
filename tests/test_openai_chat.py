"""Tests for openai_chat.py — OpenAIChatSession, transcribe(), synthesize()."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from idotmatrix_upload.openai_chat import OpenAIChatSession, synthesize, transcribe


# ---------------------------------------------------------------------------
# OpenAIChatSession — message management
# ---------------------------------------------------------------------------


class TestOpenAIChatSessionMessages:
    def test_initial_message_count(self):
        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._messages = []
        assert session.message_count == 0

    def test_add_user_message(self):
        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._messages = []
        session.add_user_message("Hello")
        assert session._messages == [{"role": "user", "content": "Hello"}]

    def test_add_assistant_message(self):
        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._messages = []
        session.add_assistant_message("Hi there!")
        assert session._messages == [{"role": "assistant", "content": "Hi there!"}]

    def test_message_history_grows(self):
        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._messages = []
        session.add_user_message("One")
        session.add_assistant_message("Two")
        session.add_user_message("Three")
        assert session.message_count == 3
        assert session._messages[0]["role"] == "user"
        assert session._messages[1]["role"] == "assistant"
        assert session._messages[2]["role"] == "user"

    def test_message_count_property(self):
        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._messages = [{"role": "user", "content": "x"}] * 4
        assert session.message_count == 4


# ---------------------------------------------------------------------------
# OpenAIChatSession — stream_response
# ---------------------------------------------------------------------------


class TestOpenAIChatSessionStream:
    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        """stream_response() should yield text deltas from the OpenAI stream."""

        async def _fake_stream():
            for text in ["Hello", ", ", "world!"]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = text
                yield chunk

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())

        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._client = mock_client
        session._model = "gpt-4o"
        session._max_tokens = 512
        session._temperature = 0.7
        session._messages = [{"role": "user", "content": "Hi"}]

        chunks = []
        async for chunk in session.stream_response():
            chunks.append(chunk)

        assert chunks == ["Hello", ", ", "world!"]

    @pytest.mark.asyncio
    async def test_stream_skips_none_deltas(self):
        """None content deltas (role-only chunks) should be filtered out."""

        async def _fake_stream():
            for text in [None, "Hi", None]:
                chunk = MagicMock()
                chunk.choices = [MagicMock()]
                chunk.choices[0].delta.content = text
                yield chunk

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())

        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._client = mock_client
        session._model = "gpt-4o"
        session._max_tokens = 512
        session._temperature = 0.7
        session._messages = [{"role": "user", "content": "Hi"}]

        chunks = []
        async for chunk in session.stream_response():
            chunks.append(chunk)

        assert chunks == ["Hi"]

    @pytest.mark.asyncio
    async def test_stream_includes_system_prompt(self):
        """The OpenAI call should include the system prompt as first message."""

        async def _fake_stream():
            return
            yield  # make it an async generator

        captured_messages: list = []

        async def mock_create(**kwargs):
            captured_messages.extend(kwargs["messages"])
            return _fake_stream()

        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_create

        session = OpenAIChatSession.__new__(OpenAIChatSession)
        session._client = mock_client
        session._model = "gpt-4o"
        session._max_tokens = 512
        session._temperature = 0.7
        session._messages = [{"role": "user", "content": "Test"}]

        async for _ in session.stream_response():
            pass

        assert captured_messages[0]["role"] == "system"
        assert "Grot" in captured_messages[0]["content"]


# ---------------------------------------------------------------------------
# transcribe()
# ---------------------------------------------------------------------------


class TestTranscribe:
    @pytest.mark.asyncio
    async def test_returns_transcribed_text(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value="hello world")

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            result = await transcribe(b"fake-wav-data", api_key="test-key")

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_strips_whitespace(self):
        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value="  hello  ")

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            result = await transcribe(b"fake-wav-data", api_key="test-key")

        assert result == "hello"

    @pytest.mark.asyncio
    async def test_returns_empty_string_on_bad_request(self):
        import openai as _openai

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(
            side_effect=_openai.BadRequestError(
                message="Audio too short",
                response=MagicMock(status_code=400),
                body={"error": {"message": "Audio too short", "type": "invalid_request_error"}},
            )
        )

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            result = await transcribe(b"", api_key="test-key")

        assert result == ""

    @pytest.mark.asyncio
    async def test_sends_wav_file_with_correct_name(self):
        mock_client = MagicMock()

        captured_kwargs: dict = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return "ok"

        mock_client.audio.transcriptions.create = mock_create

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            await transcribe(b"fake-wav", api_key="test-key")

        assert captured_kwargs["model"] == "gpt-4o-transcribe"
        assert hasattr(captured_kwargs["file"], "name")
        assert captured_kwargs["file"].name == "recording.wav"


# ---------------------------------------------------------------------------
# synthesize()
# ---------------------------------------------------------------------------


class TestSynthesize:
    @pytest.mark.asyncio
    async def test_returns_audio_bytes(self):
        fake_audio = b"RIFF\x00\x00\x00\x00WAVEfmt "
        mock_response = MagicMock()
        mock_response.read.return_value = fake_audio

        mock_client = MagicMock()
        mock_client.audio.speech.create = AsyncMock(return_value=mock_response)

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            result = await synthesize("Hello Grot!", api_key="test-key")

        assert result == fake_audio

    @pytest.mark.asyncio
    async def test_uses_wav_response_format(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"audio"
        captured_kwargs: dict = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = MagicMock()
        mock_client.audio.speech.create = mock_create

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            await synthesize("test", api_key="test-key", voice="nova")

        assert captured_kwargs["response_format"] == "wav"
        assert captured_kwargs["voice"] == "nova"
        assert captured_kwargs["model"] == "gpt-4o-mini-tts"

    @pytest.mark.asyncio
    async def test_voice_instructions_sent(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"audio"
        captured_kwargs: dict = {}

        async def mock_create(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_response

        mock_client = MagicMock()
        mock_client.audio.speech.create = mock_create

        with patch("idotmatrix_upload.openai_chat.openai.AsyncOpenAI", return_value=mock_client):
            await synthesize("test", api_key="test-key", voice_instructions="Be cheerful")

        extra = captured_kwargs.get("extra_body", {})
        assert extra.get("instructions") == "Be cheerful"
