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


def fake_transcribe_silent(_audio: Path, **_kwargs: object) -> Iterator[Segment]:
    """Return no segments at all (no speech detected)."""
    return iter([])


def fake_recognize(_image: Path) -> str:
    """Return fixed OCR text."""
    return 'Hello OCR'


def fake_recognize_traditional(_image: Path) -> str:
    """Return OCR text in traditional Chinese."""
    return '簡體中文與繁體中文'


def fake_recognize_empty(_image: Path) -> str:
    """Return no text at all (nothing detected)."""
    return ''


def fake_recognize_selective(image: Path) -> str:
    """Fail on bad.png, succeed on everything else."""
    if image.name == 'bad.png':
        raise RuntimeError('boom')
    return 'Hello OCR'


def fake_convert_docx(_source: Path, _output: Path) -> str:
    """Return fixed Markdown content."""
    return '# Doc'


def fake_convert_docx_empty(_source: Path, _output: Path) -> str:
    """Return no Markdown content at all (nothing detected)."""
    return ''


def fake_convert_docx_failing(source: Path, output: Path) -> str:
    """Create a leftover assets directory, then fail."""
    output.parent.joinpath(f'{output.stem}_files').mkdir(parents=True, exist_ok=True)
    raise RuntimeError('boom')


def make_video(path: Path) -> Path:
    """Create a fake video file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fake video data')
    return path


def make_image(path: Path) -> Path:
    """Create a fake image file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fake image data')
    return path


def make_docx(path: Path) -> Path:
    """Create a fake docx file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fake docx data')
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


def test_cli_rejects_unsupported_media(tmp_path: Path) -> None:
    """An unsupported extension fails with exit code 1."""
    src = tmp_path / 'notes.pdf'
    src.write_text('not a media file')
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'not a supported media file' in result.output


def test_cli_accepts_audio_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An audio file goes through the same pipeline and yields the same SRT."""
    src = make_video(tmp_path / 'song.mp3')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    dst = src.with_suffix('.srt')
    assert dst.read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_empty_result_writes_empty_srt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero segments produce an empty .srt plus a 'no speech detected' hint."""
    src = make_video(tmp_path / 'silence.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe_silent)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert 'no speech detected' in result.output
    assert src.with_suffix('.srt').read_text(encoding='utf-8') == ''


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


def _make_media_dir(tmp_path: Path) -> Path:
    """Create a source directory with top-level and nested media files."""
    src = tmp_path / 'videos'
    make_video(src / 'a.mp4')
    make_video(src / 'b.mkv')
    make_video(src / 'song.mp3')
    make_video(src / 'sub' / 'c.mp4')
    (src / 'notes.txt').write_text('not a media file')
    return src


def test_cli_directory_default_dst_next_to_media(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Directory mode without DST writes each .srt next to its media file."""
    src = _make_media_dir(tmp_path)
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (src / 'b.srt').is_file()
    assert (src / 'song.srt').is_file()
    assert not (src / 'sub' / 'c.srt').exists()
    assert not (src / 'notes.srt').exists()


def test_cli_directory_dst_flat_without_recursive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without -r only top-level media files are converted into DST."""
    src = _make_media_dir(tmp_path)
    dst = tmp_path / 'out'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (dst / 'b.srt').is_file()
    assert (dst / 'song.srt').is_file()
    assert not (dst / 'c.srt').exists()
    assert not (src / 'a.srt').exists()


def test_cli_directory_recursive_mirrors_structure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """-r mirrors the source structure under DST, including nested media."""
    src = _make_media_dir(tmp_path)
    dst = tmp_path / 'out'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst), '--recursive'])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (dst / 'b.srt').is_file()
    assert (dst / 'song.srt').is_file()
    assert (dst / 'sub' / 'c.srt').is_file()


def test_cli_directory_recursive_without_dst_keeps_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """-r without DST writes nested media's .srt in their own directory."""
    src = _make_media_dir(tmp_path)
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), '--recursive'])
    assert result.exit_code == 0
    assert (src / 'sub' / 'c.srt').read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_directory_skips_existing_unless_forced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing outputs are skipped by default and overwritten with --force."""
    src = _make_media_dir(tmp_path)
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
    """A failing media file does not stop the batch and is reported at the end."""
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


def test_cli_directory_no_media(tmp_path: Path) -> None:
    """A directory without media files prints a hint and exits 0."""
    src = tmp_path / 'empty'
    src.mkdir()
    (src / 'notes.txt').write_text('not a media file')
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert 'no media files found' in result.output


def test_cli_directory_stem_conflict_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Audio and video sharing a stem conflict on the same output file."""
    src = tmp_path / 'videos'
    make_video(src / 'song.mp3')
    make_video(src / 'song.mp4')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'conflicting output files' in result.output
    assert 'song.mp3' in result.output
    assert 'song.mp4' in result.output
    assert not (src / 'song.srt').exists()


def test_cli_directory_dst_must_be_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Directory mode with a DST that exists as a file fails with exit code 1."""
    src = _make_media_dir(tmp_path)
    dst = tmp_path / 'out.srt'
    dst.write_text('existing file')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 1
    assert 'not a directory' in result.output


def test_cli_directory_creates_dst(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing DST directory is created automatically."""
    src = _make_media_dir(tmp_path)
    dst = tmp_path / 'created' / 'nested'
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert (dst / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED


def test_cli_image_writes_txt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An image is OCR-converted into a .txt next to it by default."""
    src = make_image(tmp_path / 'photo.png')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    dst = src.with_suffix('.txt')
    assert dst.is_file()
    assert dst.read_text(encoding='utf-8') == 'Hello OCR'
    assert 'Loading model' not in result.output


def test_cli_image_explicit_dst_is_used_as_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit .txt DST receives the OCR content verbatim."""
    src = make_image(tmp_path / 'photo.png')
    dst = tmp_path / 'out.txt'
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert dst.read_text(encoding='utf-8') == 'Hello OCR'


def test_cli_image_rejects_non_txt_dst(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An image DST with a non-.txt extension fails with exit code 1."""
    src = make_image(tmp_path / 'photo.png')
    dst = tmp_path / 'out.srt'
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 1
    assert 'use .txt' in result.output


def test_cli_image_uppercase_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Image extension matching is case-insensitive."""
    src = make_image(tmp_path / 'PHOTO.PNG')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert src.with_suffix('.txt').is_file()


def test_cli_image_empty_result_writes_empty_txt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No detected text produces an empty .txt plus a 'no text detected' hint."""
    src = make_image(tmp_path / 'blank.png')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize_empty)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert 'no text detected' in result.output
    assert src.with_suffix('.txt').read_text(encoding='utf-8') == ''


def test_cli_image_han_simplified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--han simplified converts the OCR output to simplified Chinese."""
    src = make_image(tmp_path / 'photo.png')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize_traditional)
    result = runner.invoke(app, [str(src), '--han', 'simplified'])
    assert result.exit_code == 0
    assert src.with_suffix('.txt').read_text(encoding='utf-8') == '简体中文与繁体中文'


def test_cli_image_conversion_failure_exits_nonzero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OCR errors are reported cleanly instead of a traceback."""
    src = make_image(tmp_path / 'bad.png')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize_selective)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'conversion failed' in result.output


def test_cli_directory_mixed_media(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mixed directory yields .srt for audio/video and .txt for images."""
    src = tmp_path / 'media'
    make_video(src / 'a.mp4')
    make_image(src / 'b.png')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (src / 'b.txt').read_text(encoding='utf-8') == 'Hello OCR'
    assert 'Loading model' in result.output


def test_cli_directory_images_only_skips_model_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An image-only directory does not print the ASR model loading hint."""
    src = tmp_path / 'media'
    make_image(src / 'a.png')
    make_image(src / 'b.jpg')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.txt').read_text(encoding='utf-8') == 'Hello OCR'
    assert (src / 'b.txt').is_file()
    assert 'Loading model' not in result.output


def test_cli_directory_image_failure_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing image does not stop the batch and is reported at the end."""
    src = tmp_path / 'media'
    make_image(src / 'bad.png')
    make_image(src / 'good.png')
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize_selective)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert (src / 'good.txt').is_file()
    assert not (src / 'bad.txt').exists()
    assert 'Failed files:' in result.output
    assert 'bad.png' in result.output


def test_cli_docx_writes_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A docx file is converted into a .md next to it by default."""
    src = make_docx(tmp_path / 'doc.docx')
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    dst = src.with_suffix('.md')
    assert dst.is_file()
    assert dst.read_text(encoding='utf-8') == '# Doc'
    assert 'Loading model' not in result.output


def test_cli_docx_explicit_dst_is_used_as_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit .md DST receives the Markdown content verbatim."""
    src = make_docx(tmp_path / 'doc.docx')
    dst = tmp_path / 'out.md'
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 0
    assert dst.read_text(encoding='utf-8') == '# Doc'


def test_cli_docx_rejects_non_md_dst(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A docx DST with a non-.md extension fails with exit code 1."""
    src = make_docx(tmp_path / 'doc.docx')
    dst = tmp_path / 'out.txt'
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx)
    result = runner.invoke(app, [str(src), str(dst)])
    assert result.exit_code == 1
    assert 'use .md' in result.output


def test_cli_docx_empty_result_writes_empty_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty document produces an empty .md plus a 'no content detected' hint."""
    src = make_docx(tmp_path / 'blank.docx')
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx_empty)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert 'no content detected' in result.output
    assert src.with_suffix('.md').read_text(encoding='utf-8') == ''


def test_cli_docx_failure_cleans_assets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed docx conversion leaves neither the .md nor the assets directory."""
    src = make_docx(tmp_path / 'bad.docx')
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx_failing)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 1
    assert 'conversion failed' in result.output
    assert not (tmp_path / 'bad.md').exists()
    assert not (tmp_path / 'bad_files').exists()


def test_cli_directory_all_media_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mixed directory yields .srt, .txt and .md outputs per media type."""
    src = tmp_path / 'media'
    make_video(src / 'a.mp4')
    make_image(src / 'b.png')
    make_docx(src / 'c.docx')
    make_docx(src / 'sub' / 'd.docx')
    monkeypatch.setattr('any2txt.cli.transcribe', fake_transcribe)
    monkeypatch.setattr('any2txt.cli.recognize', fake_recognize)
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.srt').read_text(encoding='utf-8') == SRT_EXPECTED
    assert (src / 'b.txt').read_text(encoding='utf-8') == 'Hello OCR'
    assert (src / 'c.md').read_text(encoding='utf-8') == '# Doc'
    assert not (src / 'sub' / 'd.md').exists()
    assert 'Loading model' in result.output


def test_cli_directory_docx_only_skips_model_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A docx-only directory does not print the ASR model loading hint."""
    src = tmp_path / 'media'
    make_docx(src / 'a.docx')
    make_docx(src / 'b.docx')
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx)
    result = runner.invoke(app, [str(src)])
    assert result.exit_code == 0
    assert (src / 'a.md').is_file()
    assert (src / 'b.md').is_file()
    assert 'Loading model' not in result.output


def test_cli_directory_docx_failure_cleans_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing docx in a batch leaves no partial output or assets behind."""
    src = tmp_path / 'media'
    make_docx(src / 'bad.docx')
    make_docx(src / 'good.docx')
    monkeypatch.setattr('any2txt.cli.convert_docx', fake_convert_docx_failing)
    result = runner.invoke(app, [str(src), '--force'])
    assert result.exit_code == 1
    assert 'Failed files:' in result.output
    assert not (src / 'bad.md').exists()
    assert not (src / 'bad_files').exists()
