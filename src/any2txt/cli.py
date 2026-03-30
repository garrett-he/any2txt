"""CLI for any2txt.

Two output modes share one conversion pipeline: writing files (default)
and ``--stdout``, which is the machine interface used by other programs.
In stdout mode only the extracted text reaches stdout; progress, warnings,
and errors always go to stderr.
"""

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from any2txt import __version__
from any2txt.asr.faster_whisper import transcribe
from any2txt.assets import AssetMode, AssetSink, assets_dir_for, make_sink
from any2txt.docx import convert_docx
from any2txt.excel import convert_excel
from any2txt.formats.markdown import html_to_markdown
from any2txt.formats.srt import DEFAULT_LINE_WIDTH, DEFAULT_MAX_LINES, format_srt
from any2txt.media import is_supported
from any2txt.media.docx import is_docx
from any2txt.media.excel import is_excel
from any2txt.media.html import is_html, read_html, rewrite_local_images
from any2txt.media.image import is_image
from any2txt.media.pdf import is_pdf
from any2txt.media.pptx import is_pptx
from any2txt.ocr import recognize
from any2txt.pdf import convert_pdf
from any2txt.pptx import convert_pptx
from any2txt.text import HanVariant, convert_han

EXIT_FAILED = 1
EXIT_UNSUPPORTED = 2

app = typer.Typer()


def _version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        typer.echo(f'any2txt {__version__}')
        raise typer.Exit


@dataclass(frozen=True)
class _Options:
    """Conversion options shared by single-file and directory modes."""

    text_han: HanVariant
    srt_line_width: int
    srt_max_lines: int
    asr_model: str
    asr_language: str | None


def _render_srt(source: Path, options: _Options) -> str:
    """Transcribe one media file and return its rendered SRT text."""
    text = format_srt(
        transcribe(source, model_size=options.asr_model, language=options.asr_language),
        line_width=options.srt_line_width,
        max_lines=options.srt_max_lines,
    )
    text = convert_han(text, options.text_han)
    if not text:
        typer.echo('no speech detected', err=True)
    return text


def _render_txt(source: Path, options: _Options) -> str:
    """Recognize one image file and return its plain text."""
    text = convert_han(recognize(source), options.text_han)
    if not text:
        typer.echo('no text detected', err=True)
    return text


def _render_html(source: Path, sink: AssetSink) -> str:
    """Render one HTML file as Markdown, handing local images to the sink."""
    html = rewrite_local_images(read_html(source), source, sink)
    text = html_to_markdown(html).strip('\n')
    if not text.strip():
        typer.echo('no content detected', err=True)
        return ''
    return text


def _render(source: Path, sink: AssetSink, options: _Options) -> str:
    """Convert one media file to text, dispatching by media type."""
    if is_docx(source):
        text = convert_docx(source, sink)
        if not text:
            typer.echo('no content detected', err=True)
        return text
    if is_pptx(source):
        text = convert_pptx(source, sink)
        if not text:
            typer.echo('no content detected', err=True)
        return text
    if is_pdf(source):
        text = convert_pdf(source, sink)
        if not text:
            typer.echo('no content detected', err=True)
        return text
    if is_html(source):
        return _render_html(source, sink)
    if is_excel(source):
        text = convert_excel(source, sink)
        if not text:
            typer.echo('no content detected', err=True)
        return text
    if is_image(source):
        return _render_txt(source, options)
    return _render_srt(source, options)


def _convert_one(source: Path, output: Path, options: _Options, assets: AssetMode) -> None:
    """Convert one media file and write its output text file."""
    output.write_text(_render(source, make_sink(assets, output), options), encoding='utf-8')


def _collect_media(src: Path, recursive: bool) -> list[Path]:
    """Return the supported media files directly under src, or recursively."""
    candidates = src.rglob('*') if recursive else src.iterdir()
    return sorted(path for path in candidates if path.is_file() and is_supported(path))


def _output_path(media: Path, src: Path, dst: Path | None, recursive: bool, suffix: str) -> Path:
    """Return the output path for one media file in directory mode."""
    if dst is None:
        return media.with_suffix(suffix)
    relative = media.relative_to(src) if recursive else Path(media.name)
    return dst / relative.with_suffix(suffix)


def _output_suffix(media: Path) -> str:
    """Return the output file extension for one media file."""
    if is_docx(media) or is_html(media) or is_pptx(media) or is_excel(media) or is_pdf(media):
        return '.md'
    return '.txt' if is_image(media) else '.srt'


def _needs_asr(media: Path) -> bool:
    """Return True if a media file goes through the ASR pipeline."""
    return not (
        is_image(media) or is_docx(media) or is_html(media) or is_pptx(media) or is_excel(media) or is_pdf(media)
    )


def _has_assets(media: Path) -> bool:
    """Return True if a media file extracts resources into an assets directory."""
    return is_docx(media) or is_html(media) or is_pptx(media) or is_pdf(media) or is_excel(media)


def _convert_directory(
    src: Path,
    dst: Path | None,
    options: _Options,
    recursive: bool,
    force: bool,
    assets: AssetMode,
) -> int:
    """Convert every media file under src; return the process exit code."""
    if dst is not None and dst.exists() and not dst.is_dir():
        typer.echo(f'Error: output path {dst} is not a directory', err=True)
        return EXIT_FAILED
    media_files = _collect_media(src, recursive)
    if not media_files:
        typer.echo('no media files found', err=True)
        return 0
    jobs = [(media, _output_path(media, src, dst, recursive, _output_suffix(media))) for media in media_files]
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
            typer.echo(f'  {first} and {second} both write {second.with_suffix(_output_suffix(second))}', err=True)
        return EXIT_FAILED
    if any(_needs_asr(media) for media, _ in jobs):
        typer.echo('Loading model (first use of a model size downloads it)...', err=True)
    total = len(jobs)
    converted = skipped = 0
    failures: list[tuple[Path, str]] = []
    for position, (media, output) in enumerate(jobs, start=1):
        typer.echo(f'Processing {position}/{total}: {media}', err=True)
        if output.exists() and not force:
            typer.echo(f'Skipping {output} (already exists)', err=True)
            skipped += 1
            continue
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            _convert_one(media, output, options, assets)
        except Exception as exc:
            output.unlink(missing_ok=True)
            if assets is AssetMode.DIR and _has_assets(media):
                shutil.rmtree(assets_dir_for(output), ignore_errors=True)
            failures.append((media, str(exc)))
            typer.echo(f'Failed: {media}: {exc}', err=True)
        else:
            converted += 1
    typer.echo(f'Done: {converted} converted, {skipped} skipped, {len(failures)} failed', err=True)
    if failures:
        typer.echo('Failed files:', err=True)
        for media, message in failures:
            typer.echo(f'  {media}: {message}', err=True)
        return EXIT_FAILED
    return 0


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option('--version', callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Convert media files: video/audio to SRT, images to text, documents to Markdown."""


@app.command('transcribe')
def main(
    src: Annotated[Path, typer.Argument(help='Path to a media file, or a directory of media files.')],
    dst: Annotated[
        Path | None,
        typer.Argument(help='Output .txt or .srt path (file mode) or output directory (directory mode).'),
    ] = None,
    stdout: Annotated[
        bool,
        typer.Option('--stdout', help='Write the extracted text to stdout instead of a file (single input only).'),
    ] = False,
    assets: Annotated[
        AssetMode | None,
        typer.Option(
            '--assets',
            help='Extracted images and embedded objects: dir (files next to the output), drop (omit them), '
            'embed (inline data URIs). Defaults to dir, or drop when using --stdout.',
        ),
    ] = None,
    text_han: Annotated[
        HanVariant,
        typer.Option(
            '--text-han',
            help='Chinese script variant of SRT/text output (ignored for document formats): auto, '
            'simplified or traditional.',
        ),
    ] = HanVariant.AUTO,
    srt_line_width: Annotated[
        int,
        typer.Option(
            '--srt-line-width',
            min=1,
            help='Maximum display width per subtitle line; full-width chars count as 2.',
        ),
    ] = DEFAULT_LINE_WIDTH,
    srt_max_lines: Annotated[
        int,
        typer.Option(
            '--srt-max-lines',
            min=1,
            help='Maximum lines per subtitle cue; longer segments are split into multiple cues.',
        ),
    ] = DEFAULT_MAX_LINES,
    asr_model: Annotated[
        str,
        typer.Option(
            '--asr-model',
            help='Whisper model size (tiny, base, small, medium, ...); first use downloads it.',
        ),
    ] = 'base',
    asr_language: Annotated[
        str | None,
        typer.Option(
            '--asr-language',
            help='ISO language code of the audio (e.g. zh); omitted means auto-detect.',
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option('--recursive', '-r', help='Process media files in subdirectories as well.'),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            '--force',
            '-f',
            help='Re-convert media files whose output already exists (directory mode).',
        ),
    ] = False,
) -> None:
    """Convert media files: video/audio to SRT, images to text, documents to Markdown.

    SRC may be a media file or a directory of media files. With a
    directory, every file is converted next to it (or into DST when
    given); ``--force`` re-converts files whose output exists.

    With ``--stdout`` the text is written to stdout and nothing is
    written to disk, which is the interface intended for other programs.
    Exit codes: 0 success, 1 failure, 2 unsupported input.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8')
    options = _Options(
        text_han=text_han,
        srt_line_width=srt_line_width,
        srt_max_lines=srt_max_lines,
        asr_model=asr_model,
        asr_language=asr_language,
    )
    if stdout:
        raise typer.Exit(_run_stdout(src, dst, assets, options))
    mode = AssetMode.DIR if assets is None else assets
    if src.is_dir():
        raise typer.Exit(_convert_directory(src, dst, options, recursive, force, mode))
    if not src.is_file():
        typer.echo(f'Error: source not found: {src}', err=True)
        raise typer.Exit(EXIT_FAILED)
    if not is_supported(src):
        typer.echo(f'Error: not a supported media file: {src}', err=True)
        raise typer.Exit(EXIT_UNSUPPORTED)
    suffix = _output_suffix(src)
    if dst is not None and dst.suffix.lower() != suffix:
        typer.echo(f'Error: unsupported output extension {dst.suffix!r}; use {suffix}', err=True)
        raise typer.Exit(EXIT_FAILED)
    output = dst if dst is not None else src.with_suffix(suffix)
    if _needs_asr(src):
        typer.echo('Loading model (first use of a model size downloads it)...', err=True)
    try:
        text = _render(src, make_sink(mode, output), options)
    except Exception as exc:
        if mode is AssetMode.DIR and _has_assets(src):
            shutil.rmtree(assets_dir_for(output), ignore_errors=True)
        typer.echo(f'Error: conversion failed: {exc}', err=True)
        raise typer.Exit(EXIT_FAILED) from None
    try:
        output.write_text(text, encoding='utf-8')
    except OSError as exc:
        typer.echo(f'Error: cannot write output file {output}: {exc}', err=True)
        raise typer.Exit(EXIT_FAILED) from None
    typer.echo(f'Transcript written to {output}', err=True)


def _run_stdout(src: Path, dst: Path | None, assets: AssetMode | None, options: _Options) -> int:
    """Extract one file to stdout; return the process exit code."""
    mode = AssetMode.DROP if assets is None else assets
    if dst is not None:
        typer.echo('Error: --stdout cannot be combined with an output path', err=True)
        return EXIT_FAILED
    if mode is AssetMode.DIR:
        typer.echo('Error: --assets dir writes files and cannot be combined with --stdout', err=True)
        return EXIT_FAILED
    if src.is_dir():
        typer.echo('Error: --stdout accepts a single media file, not a directory', err=True)
        return EXIT_FAILED
    if not src.is_file():
        typer.echo(f'Error: source not found: {src}', err=True)
        return EXIT_FAILED
    if not is_supported(src):
        typer.echo(f'Error: not a supported media file: {src}', err=True)
        return EXIT_UNSUPPORTED
    if _needs_asr(src):
        typer.echo('Loading model (first use of a model size downloads it)...', err=True)
    try:
        text = _render(src, make_sink(mode, None), options)
    except Exception as exc:
        typer.echo(f'Error: conversion failed: {exc}', err=True)
        return EXIT_FAILED
    if text:
        sys.stdout.write(text if text.endswith('\n') else f'{text}\n')
    return 0
