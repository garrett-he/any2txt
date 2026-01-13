"""Tests for any2txt.media.video."""

from pathlib import Path

from any2txt.media.video import is_video


def test_is_video_known_extensions() -> None:
    """Common video extensions are recognized."""
    assert is_video(Path('a.mp4'))
    assert is_video(Path('a.mkv'))
    assert is_video(Path('a.MP4'))
    assert is_video(Path('a.Mkv'))


def test_is_video_rejects_other_extensions() -> None:
    """Non-video extensions are rejected."""
    assert not is_video(Path('a.txt'))
    assert not is_video(Path('a.md'))
    assert not is_video(Path('a'))
    assert not is_video(Path('a.mp4.txt'))
