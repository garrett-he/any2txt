"""CLI for any2txt."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from any2txt import __version__
from any2txt.asr.faster_whisper import transcribe
from any2txt.formats.srt import DEFAULT_LINE_WIDTH, DEFAULT_MAX_LINES, format_srt
from any2txt.media.video import is_video
from any2txt.text import HanVariant, convert_han

app = typer.Typer()


def _version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        typer.echo(f'any2txt {__version__}')
        raise typer.Exit


@dataclass(frozen=True)
class _Options:
    """Conversion options shared by single-file and directory modes."""

    han: HanVariant
    line_width: int
    max_lines: int
    model: str
    language: str | None


def _render_srt(video: Path, options: _Options) -> str:
    """Transcribe one video and return its rendered SRT text."""
    text = format_srt(
        transcribe(video, model_size=options.model, language=options.language),
        line_width=options.line_width,
        max_lines=options.max_lines,
    )
    return convert_han(text, options.han)


def _convert_one(video: Path, output: Path, options: _Options) -> None:
    """Transcribe one video and write its SRT file."""
    output.write_text(_render_srt(video, options), encoding='utf-8')


def _collect_videos(src: Path, recursive: bool) -> list[Path]:
    """Return the videos directly under src, or under it recursively."""
    candidates = src.rglob('*') if recursive else src.iterdir()
    return sorted(path for path in candidates if path.is_file() and is_video(path))


def _convert_directory(
    src: Path,
    dst: Path | None,
    options: _Options,
    recursive: bool,
    force: bool,
) -> int:
    """Convert every video under src; return the process exit code."""
    if dst is not None and dst.exists() and not dst.is_dir():
        typer.echo(f'Error: output path {dst} is not a directory', err=True)
        return 1
    videos = _collect_videos(src, recursive)
    if not videos:
        typer.echo('no video files found')
        return 0
    typer.echo('Loading model (first use of a model size downloads it)...')
    total = len(videos)
    converted = skipped = 0
    failures: list[tuple[Path, str]] = []
    for position, video in enumerate(videos, start=1):
        if dst is None:
            output = video.with_suffix('.srt')
        else:
            relative = video.relative_to(src) if recursive else Path(video.name)
            output = dst / relative.with_suffix('.srt')
        typer.echo(f'Processing {position}/{total}: {video}')
        if output.exists() and not force:
            typer.echo(f'Skipping {output} (already exists)')
            skipped += 1
            continue
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            _convert_one(video, output, options)
        except Exception as exc:
            output.unlink(missing_ok=True)
            failures.append((video, str(exc)))
            typer.echo(f'Failed: {video}: {exc}', err=True)
        else:
            converted += 1
    typer.echo(f'Done: {converted} converted, {skipped} skipped, {len(failures)} failed')
    if failures:
        typer.echo('Failed files:', err=True)
        for video, message in failures:
            typer.echo(f'  {video}: {message}', err=True)
        return 1
    return 0


@app.command()
def main(
    src: Annotated[Path, typer.Argument(help='Path to a video file, or a directory of videos.')],
    dst: Annotated[
        Path | None,
        typer.Argument(help='Output .srt path (file mode) or output directory (directory mode).'),
    ] = None,
    han: Annotated[
        HanVariant,
        typer.Option(
            '--han',
            help='Chinese script variant of the output: auto (keep ASR output), simplified or traditional.',
        ),
    ] = HanVariant.AUTO,
    line_width: Annotated[
        int,
        typer.Option(
            '--line-width',
            min=1,
            help='Maximum display width per subtitle line; full-width chars count as 2.',
        ),
    ] = DEFAULT_LINE_WIDTH,
    max_lines: Annotated[
        int,
        typer.Option(
            '--max-lines',
            min=1,
            help='Maximum lines per subtitle cue; longer segments are split into multiple cues.',
        ),
    ] = DEFAULT_MAX_LINES,
    model: Annotated[
        str,
        typer.Option(
            '--model',
            help='Whisper model size (tiny, base, small, medium, ...); first use downloads it.',
        ),
    ] = 'base',
    language: Annotated[
        str | None,
        typer.Option(
            '--language',
            help='ISO language code of the audio (e.g. zh); omitted means auto-detect.',
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option('--recursive', '-r', help='Process videos in subdirectories as well.'),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            '--force',
            '-f',
            help='Re-convert videos whose output .srt already exists (directory mode).',
        ),
    ] = False,
    version: Annotated[
        bool,
        typer.Option('--version', callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Transcribe video audio into SRT subtitles.

    SRC may be a video file or a directory of videos. With a directory,
    every video is converted to ``{name}.srt`` next to it, or into DST
    when given; ``--force`` re-converts videos whose output exists.
    """
    options = _Options(
        han=han,
        line_width=line_width,
        max_lines=max_lines,
        model=model,
        language=language,
    )
    if src.is_dir():
        raise typer.Exit(_convert_directory(src, dst, options, recursive, force))
    if not src.is_file():
        typer.echo(f'Error: source not found: {src}', err=True)
        raise typer.Exit(1)
    if not is_video(src):
        typer.echo(f'Error: not a supported video file: {src}', err=True)
        raise typer.Exit(1)
    if dst is not None and dst.suffix.lower() != '.srt':
        typer.echo(f'Error: unsupported output extension {dst.suffix!r}; use .srt', err=True)
        raise typer.Exit(1)
    output = dst if dst is not None else src.with_suffix('.srt')
    typer.echo('Loading model (first use of a model size downloads it)...')
    try:
        text = _render_srt(src, options)
    except Exception as exc:
        typer.echo(f'Error: conversion failed: {exc}', err=True)
        raise typer.Exit(1) from None
    try:
        output.write_text(text, encoding='utf-8')
    except OSError as exc:
        typer.echo(f'Error: cannot write output file {output}: {exc}', err=True)
        raise typer.Exit(1) from None
    typer.echo(f'Transcript written to {output}')
