"""Tests for any2txt CLI."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from any2txt.asr import Segment
from any2txt.cli import app

runner = CliRunner()

SEGMENTS = [Segment(start=0.0, end=2.0, text='Hello.'), Segment(start=61.0, end=63.0, text='World.')]


def fake_transcribe(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a fixed set of transcription segments."""
    return iter(SEGMENTS)


def fake_transcribe_traditional(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a single segment in traditional Chinese."""
    return iter([Segment(start=0.0, end=2.0, text='簡體中文與繁體中文')])


def fake_transcribe_long(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a single segment with text exceeding the default line width."""
    return iter([Segment(start=0.0, end=5.0, text='alpha beta gamma delta')])


def fake_transcribe_failing(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Simulate a model failure."""
    raise RuntimeError('model download failed')
    yield  # pragma: no cover


@pytest.fixture
def fake_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake video file and stub out transcription."""
    src = tmp_path / 'video.mp4'
    src.write_bytes(b'fake video data')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    return src


def test_cli_writes_transcript(fake_video: Path) -> None:
    """The CLI writes the transcript to the default SRT output."""
    result = runner.invoke(app, [str(fake_video)])
    assert result.exit_code == 0
    assert fake_video.with_suffix('.srt').is_file()


def test_cli_version() -> None:
    """--version prints the package version."""
    result = runner.invoke(app, ['--version'])
    assert result.exit_code == 0
    assert result.output.startswith('any2txt ')


def test_cli_source_file_not_found(tmp_path: Path) -> None:
    """A missing source file fails with exit code 1."""
    result = runner.invoke(app, [str(tmp_path / 'missing.mp4')])
    assert result.exit_code == 1
    assert 'not found' in result.output


def test_cli_rejects_non_video(tmp_path: Path) -> None:
    """A non-video extension fails with exit code 1."""
    src = tmp_path / 'notes.txt'
    src.write_text('not a video')
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'not a supported video' in result.output


def test_cli_accepts_uppercase_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extension matching is case-insensitive."""
    src = tmp_path / 'VIDEO.MP4'
    src.write_bytes(b'fake video data')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0


def test_cli_default_dst_is_srt(fake_video: Path) -> None:
    """Without DST the transcript is written as an .srt file next to SRC."""
    result = runner.invoke(app, [str(fake_video)])
    assert result.exit_code == 0
    dst = fake_video.with_suffix('.srt')
    assert dst.is_file()
    expected = '1\n00:00:00,000 --> 00:00:02,000\nHello.\n\n2\n00:01:01,000 --> 00:01:03,000\nWorld.'
    assert dst.read_text(encoding='utf-8') == expected


def test_cli_explicit_dst_is_used_as_is(tmp_path: Path, fake_video: Path) -> None:
    """An explicit .srt DST receives the SRT content verbatim."""
    dst = tmp_path / 'out.srt'
    result = runner.invoke(app, [str(fake_video), str(dst)])
    assert result.exit_code == 0
    assert dst.is_file()
    expected = '1\n00:00:00,000 --> 00:00:02,000\nHello.\n\n2\n00:01:01,000 --> 00:01:03,000\nWorld.'
    assert dst.read_text(encoding='utf-8') == expected


def test_cli_rejects_non_srt_dst(fake_video: Path, tmp_path: Path) -> None:
    """A DST with an extension other than .srt fails with exit code 1."""
    dst = tmp_path / 'out.txt'
    result = runner.invoke(app, [str(fake_video), str(dst)])
    assert result.exit_code == 1
    assert 'use .srt' in result.output


def test_cli_transcription_failure_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Transcription errors are reported cleanly instead of a traceback."""
    src = tmp_path / 'video.mp4'
    src.write_bytes(b'fake video data')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_failing)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'transcription failed' in result.output


def test_cli_line_width_splits_segments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--line-width wraps lines; over-long segments split into timed cues."""
    src = tmp_path / 'video.mp4'
    src.write_bytes(b'fake video data')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_long)
    result = runner.invoke(app, [str(src), '--line-width', '10'])
    assert result.exit_code == 0
    dst = src.with_suffix('.srt')
    expected = '1\n00:00:00,000 --> 00:00:03,750\nalpha beta\ngamma\n\n2\n00:00:03,750 --> 00:00:05,000\ndelta'
    assert dst.read_text(encoding='utf-8') == expected


def test_cli_han_simplified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--han simplified converts the transcript to simplified Chinese."""
    src = tmp_path / 'video.mp4'
    src.write_bytes(b'fake video data')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_traditional)
    result = runner.invoke(app, [str(src), '--han', 'simplified'])
    assert result.exit_code == 0
    dst = src.with_suffix('.srt')
    expected = '1\n00:00:00,000 --> 00:00:02,000\n简体中文与繁体中文'
    assert dst.read_text(encoding='utf-8') == expected


def test_cli_han_rejects_invalid_value(fake_video: Path) -> None:
    """An invalid --han value fails with a usage error."""
    result = runner.invoke(app, [str(fake_video), '--han', 'klingon'])
    assert result.exit_code != 0
