"""CLI for any2txt."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from any2txt import __version__
from any2txt.asr.faster_whisper import transcribe
from any2txt.formats.srt import DEFAULT_LINE_WIDTH, DEFAULT_MAX_LINES, format_srt
from any2txt.media import is_supported
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


def _render_srt(source: Path, options: _Options) -> str:
    """Transcribe one media file and return its rendered SRT text."""
    text = format_srt(
        transcribe(source, model_size=options.model, language=options.language),
        line_width=options.line_width,
        max_lines=options.max_lines,
    )
    text = convert_han(text, options.han)
    if not text:
        typer.echo('no speech detected')
    return text


def _convert_one(source: Path, output: Path, options: _Options) -> None:
    """Transcribe one media file and write its SRT file."""
    output.write_text(_render_srt(source, options), encoding='utf-8')


def _collect_media(src: Path, recursive: bool) -> list[Path]:
    """Return the supported media files directly under src, or recursively."""
    candidates = src.rglob('*') if recursive else src.iterdir()
    return sorted(path for path in candidates if path.is_file() and is_supported(path))


def _output_path(video: Path, src: Path, dst: Path | None, recursive: bool) -> Path:
    """Return the SRT output path for one media file in directory mode."""
    if dst is None:
        return video.with_suffix('.srt')
    relative = video.relative_to(src) if recursive else Path(video.name)
    return dst / relative.with_suffix('.srt')


def _convert_directory(
    src: Path,
    dst: Path | None,
    options: _Options,
    recursive: bool,
    force: bool,
) -> int:
    """Convert every media file under src; return the process exit code."""
    if dst is not None and dst.exists() and not dst.is_dir():
        typer.echo(f'Error: output path {dst} is not a directory', err=True)
        return 1
    media_files = _collect_media(src, recursive)
    if not media_files:
        typer.echo('no media files found')
        return 0
    jobs = [(media, _output_path(media, src, dst, recursive)) for media in media_files]
    outputs_seen: dict[Path, Path] = {}
    conflicts: list[tuple[Path, Path]] = []
    for media, output in jobs:
        if output in outputs_seen:
            conflicts.append((outputs_seen[output], media))
        else:
            outputs_seen[output] = media
    if conflicts:
        typer.echo('Error: conflicting output files:', err=True)
        for first, second in conflicts:
            typer.echo(f'  {first} and {second} both write {second.with_suffix(".srt")}', err=True)
        return 1
    typer.echo('Loading model (first use of a model size downloads it)...')
    total = len(jobs)
    converted = skipped = 0
    failures: list[tuple[Path, str]] = []
    for position, (media, output) in enumerate(jobs, start=1):
        typer.echo(f'Processing {position}/{total}: {media}')
        if output.exists() and not force:
            typer.echo(f'Skipping {output} (already exists)')
            skipped += 1
            continue
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            _convert_one(media, output, options)
        except Exception as exc:
            output.unlink(missing_ok=True)
            failures.append((media, str(exc)))
            typer.echo(f'Failed: {media}: {exc}', err=True)
        else:
            converted += 1
    typer.echo(f'Done: {converted} converted, {skipped} skipped, {len(failures)} failed')
    if failures:
        typer.echo('Failed files:', err=True)
        for media, message in failures:
            typer.echo(f'  {media}: {message}', err=True)
        return 1
    return 0


@app.command()
def main(
    src: Annotated[Path, typer.Argument(help='Path to a media file, or a directory of media files.')],
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
    """Transcribe the audio of a video or audio file into SRT subtitles.

    SRC may be a media file or a directory of media files. With a
    directory, every file is converted to ``{name}.srt`` next to it, or
    into DST when given; ``--force`` re-converts files whose output
    exists.
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
    if not is_supported(src):
        typer.echo(f'Error: not a supported video or audio file: {src}', err=True)
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
