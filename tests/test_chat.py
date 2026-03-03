from __future__ import annotations

import pytest

from idotmatrix_upload.animations import AnimationState
from idotmatrix_upload.chat import extract_mood, strip_mood_tag


# ---------------------------------------------------------------------------
# extract_mood
# ---------------------------------------------------------------------------


class TestExtractMood:
    def test_talking(self):
        assert extract_mood("Hello there!\n[mood:talking]") == AnimationState.TALKING

    def test_excited(self):
        assert extract_mood("Wow!\n[mood:excited]") == AnimationState.EXCITED

    def test_thinking(self):
        assert extract_mood("Hmm...\n[mood:thinking]") == AnimationState.THINKING

    def test_idle(self):
        assert extract_mood("Ok.\n[mood:idle]") == AnimationState.IDLE

    def test_dancing(self):
        assert extract_mood("Party!\n[mood:dancing]") == AnimationState.DANCING

    def test_missing_tag_defaults_to_idle(self):
        assert extract_mood("No mood tag here.") == AnimationState.IDLE

    def test_unknown_mood_defaults_to_idle(self):
        assert extract_mood("[mood:confused]") == AnimationState.IDLE

    def test_tag_in_middle_of_text(self):
        text = "Some text before\n[mood:excited]\nand after"
        assert extract_mood(text) == AnimationState.EXCITED

    def test_empty_string(self):
        assert extract_mood("") == AnimationState.IDLE


# ---------------------------------------------------------------------------
# strip_mood_tag
# ---------------------------------------------------------------------------


class TestStripMoodTag:
    def test_strips_tag_at_end(self):
        assert strip_mood_tag("Hello!\n[mood:talking]") == "Hello!"

    def test_strips_tag_in_middle(self):
        result = strip_mood_tag("Before [mood:excited] after")
        assert "[mood:" not in result

    def test_no_tag_returns_original(self):
        text = "No tag here."
        assert strip_mood_tag(text) == text

    def test_strips_trailing_whitespace_after_removal(self):
        result = strip_mood_tag("Hello!\n[mood:idle]\n  ")
        assert result == "Hello!"

    def test_empty_string(self):
        assert strip_mood_tag("") == ""

    def test_only_mood_tag(self):
        assert strip_mood_tag("[mood:thinking]") == ""
