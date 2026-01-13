"""CLI for any2txt."""

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


@app.command()
def main(
    src: Annotated[Path, typer.Argument(help='Path to the source video file.')],
    dst: Annotated[
        Path | None,
        typer.Argument(help='Path to the output SRT file.'),
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
    version: Annotated[
        bool,
        typer.Option('--version', callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """Transcribe the audio track of a video file into an SRT subtitle file.

    When DST is omitted, the subtitle file is written next to SRC as
    ``{SRC name without extension}.srt``.
    """
    if not src.is_file():
        typer.echo(f'Error: source file not found: {src}', err=True)
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
        text = format_srt(
            transcribe(src, model_size=model, language=language),
            line_width=line_width,
            max_lines=max_lines,
        )
    except Exception as exc:
        typer.echo(f'Error: transcription failed: {exc}', err=True)
        raise typer.Exit(1) from None
    text = convert_han(text, han)
    try:
        output.write_text(text, encoding='utf-8')
    except OSError as exc:
        typer.echo(f'Error: cannot write output file {output}: {exc}', err=True)
        raise typer.Exit(1) from None
    typer.echo(f'Transcript written to {output}')
