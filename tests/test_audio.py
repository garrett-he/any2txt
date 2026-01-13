"""Tests for any2txt.media.audio."""

from pathlib import Path

from any2txt.media.audio import is_audio


def test_is_audio_known_extensions() -> None:
    """Common audio extensions are recognized."""
    assert is_audio(Path('a.mp3'))
    assert is_audio(Path('a.wav'))
    assert is_audio(Path('a.flac'))
    assert is_audio(Path('a.M4A'))
    assert is_audio(Path('a.Opus'))


def test_is_audio_rejects_other_extensions() -> None:
    """Non-audio extensions are rejected."""
    assert not is_audio(Path('a.txt'))
    assert not is_audio(Path('a.mp4'))
    assert not is_audio(Path('a'))
    assert not is_audio(Path('a.mp3.txt'))
