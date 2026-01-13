"""Tests for any2txt CLI."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from any2txt.asr import Segment
from any2txt.cli import app

runner = CliRunner()

SEGMENTS = [Segment(start=0.0, end=2.0, text='Hello.'), Segment(start=61.0, end=63.0, text='World.')]

SRT_EXPECTED = '1\n00:00:00,000 --> 00:00:02,000\nHello.\n\n2\n00:01:01,000 --> 00:01:03,000\nWorld.'


def fake_transcribe(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a fixed set of transcription segments."""
    return iter(SEGMENTS)


def fake_transcribe_traditional(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a single segment in traditional Chinese."""
    return iter([Segment(start=0.0, end=2.0, text='簡體中文與繁體中文')])


def fake_transcribe_long(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return a single segment with text exceeding the default line width."""
    return iter([Segment(start=0.0, end=5.0, text='alpha beta gamma delta')])


def fake_transcribe_selective(audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Fail on bad.mp4, succeed on everything else."""
    if audio.name == 'bad.mp4':
        raise RuntimeError('boom')
    return iter(SEGMENTS)


def make_video(path: Path) -> Path:
    """Create a fake video file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fake video data')
    return path


@pytest.fixture
def fake_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a fake video file and stub out transcription."""
    src = make_video(tmp_path / 'video.mp4')
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


def test_cli_source_not_found(tmp_path: Path) -> None:
    """A missing source path fails with exit code 1."""
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
    src = make_video(tmp_path / 'VIDEO.MP4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0


def test_cli_default_dst_is_srt(fake_video: Path) -> None:
    """Without DST the transcript is written as an .srt file next to SRC."""
    result = runner.invoke(app, [str(fake_video)])
    assert result.exit_code == 0
    dst = fake_video.with_suffix('.srt')
    assert dst.is_file()
    assert dst.read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_explicit_dst_is_used_as_is(tmp_path: Path, fake_video: Path) -> None:
    """An explicit .srt DST receives the SRT content verbatim."""
    dst = tmp_path / 'out.srt'
    result = runner.invoke(app, [str(fake_video), str(dst)])
    assert result.exit_code == 0
    assert dst.is_file()
    assert dst.read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_rejects_non_srt_dst(fake_video: Path, tmp_path: Path) -> None:
    """A DST with an extension other than .srt fails with exit code 1."""
    dst = tmp_path / 'out.txt'
    result = runner.invoke(app, [str(fake_video), str(dst)])
    assert result.exit_code == 1
    assert 'use .srt' in result.output


def test_cli_conversion_failure_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Conversion errors are reported cleanly instead of a traceback."""
    src = make_video(tmp_path / 'bad.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_selective)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'conversion failed' in result.output


def test_cli_write_failure_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An unwritable output path reports a dedicated write error."""
    src = make_video(tmp_path / 'video.mp4')
    dst = tmp_path / 'dir.srt'
    dst.mkdir()
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 1
    assert 'cannot write output file' in result.output


def test_cli_directory_failure_removes_partial_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed conversion does not leave a partial .srt behind to be skipped."""
    src = tmp_path / 'videos'
    make_video(src / 'a.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    original_write = Path.write_text

    def failing_write(self: Path, data: str, **kwargs: str | None) -> int:
        original_write(self, data, **kwargs)  # create the file first
        msg = 'simulated mid-write failure'
        raise OSError(msg)

    monkeypatch.setattr(Path, 'write_text', failing_write)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert not (src / 'a.srt').exists()


def test_cli_line_width_splits_segments(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--line-width wraps lines; over-long segments split into timed cues."""
    src = make_video(tmp_path / 'video.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_long)
    result = runner.invoke(app, [str(src), '--line-width', '10'])
    assert result.exit_code == 0
    dst = src.with_suffix('.srt')
    expected = '1\n00:00:00,000 --> 00:00:03,750\nalpha beta\ngamma\n\n2\n00:00:03,750 --> 00:00:05,000\ndelta'
    assert dst.read_text(encoding='utf-8') == expected


def test_cli_han_simplified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--han simplified converts the transcript to simplified Chinese."""
    src = make_video(tmp_path / 'video.mp4')
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


def _make_video_dir(tmp_path: Path) -> Path:
    """Create a source directory with top-level and nested videos."""
    src = tmp_path / 'videos'
    make_video(src / 'a.mp4')
    make_video(src / 'b.mkv')
    make_video(src / 'sub' / 'c.mp4')
    (src / 'notes.txt').write_text('not a video')
    return src


def test_cli_directory_default_dst_next_to_videos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Directory mode without DST writes each .srt next to its video."""
    src = _make_video_dir(tmp_path)
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (src / 'b.srt').is_file()
    assert not (src / 'c.srt').exists()
    assert not (src / 'notes.srt').exists()


def test_cli_directory_dst_flat_without_recursive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without -r only top-level videos are converted into the DST directory."""
    src = _make_video_dir(tmp_path)
    dst = tmp_path / 'out'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (dst / 'b.srt').is_file()
    assert not (dst / 'c.srt').exists()
    assert not (src / 'a.srt').exists()


def test_cli_directory_recursive_mirrors_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """-r mirrors the source structure under DST, including nested videos."""
    src = _make_video_dir(tmp_path)
    dst = tmp_path / 'out'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst), '--recursive'])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (dst / 'b.srt').is_file()
    assert (dst / 'sub' / 'c.srt').is_file()


def test_cli_directory_recursive_without_dst_keeps_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """-r without DST writes nested videos' .srt in their own directory."""
    src = _make_video_dir(tmp_path)
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), '--recursive'])
    assert result.exit_code == 0
    assert (src / 'sub' / 'c.srt').read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_directory_skips_existing_unless_forced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing outputs are skipped by default and overwritten with --force."""
    src = _make_video_dir(tmp_path)
    existing = src / 'a.srt'
    existing.write_text('old content')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert existing.read_text(encoding='utf-8') == 'old content'
    assert (src / 'b.srt').is_file()
    assert 'Skipping' in result.output
    result = runner.invoke(app, [str(src), '--force'])
    assert result.exit_code == 0
    assert existing.read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_directory_failure_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing video does not stop the batch and is reported at the end."""
    src = tmp_path / 'videos'
    make_video(src / 'bad.mp4')
    make_video(src / 'good.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_selective)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert (src / 'good.srt').is_file()
    assert not (src / 'bad.srt').exists()
    assert 'Failed files:' in result.output
    assert 'bad.mp4' in result.output
    assert 'boom' in result.output


def test_cli_directory_no_videos(tmp_path: Path) -> None:
    """A directory without videos prints a hint and exits 0."""
    src = tmp_path / 'empty'
    src.mkdir()
    (src / 'notes.txt').write_text('not a video')
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert 'no video files found' in result.output


def test_cli_directory_dst_must_be_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Directory mode with a DST that exists as a file fails with exit code 1."""
    src = _make_video_dir(tmp_path)
    dst = tmp_path / 'out.srt'
    dst.write_text('existing file')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 1
    assert 'not a directory' in result.output


def test_cli_directory_creates_dst(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing DST directory is created automatically."""
    src = _make_video_dir(tmp_path)
    dst = tmp_path / 'created' / 'nested'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
