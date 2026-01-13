"""Tests for any2txt.media.image."""

from pathlib import Path

from any2txt.media.image import is_image


def test_is_image_known_extensions() -> None:
    """Common image extensions are recognized."""
    assert is_image(Path('a.png'))
    assert is_image(Path('a.jpg'))
    assert is_image(Path('a.PNG'))
    assert is_image(Path('a.WebP'))


def test_is_image_rejects_other_extensions() -> None:
    """Non-image extensions are rejected."""
    assert not is_image(Path('a.txt'))
    assert not is_image(Path('a.mp4'))
    assert not is_image(Path('a'))
    assert not is_image(Path('a.png.txt'))
