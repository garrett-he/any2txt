# any2txt

[![license](https://img.shields.io/badge/license-MIT-blue)](https://github.com/garrett-he/any2txt/blob/main/LICENSE)
[![ci](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml/badge.svg)](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml)

Transcribe video or audio files into SRT subtitles with local speech
recognition (faster-whisper). No API key, no ffmpeg required.

## Install

Requires Python 3.12+.

```sh
uv tool install any2txt
```

Or with pip:

```sh
pip install any2txt
```

## Usage

```sh
# Write video.srt next to the source file
any2txt video.mp4

# Audio works the same way
any2txt song.mp3

# Explicit output path (must end with .srt)
any2txt video.mp4 output.srt

# Convert the transcript to simplified Chinese
any2txt video.mp4 --han simplified

# Pick a bigger model and pin the language
any2txt video.mp4 --model small --language zh

# Custom line width and lines per cue
any2txt video.mp4 --line-width 42 --max-lines 2

# Convert every media file in a directory; each .srt lands next to its source
any2txt videos/

# Convert into an output directory (created if missing), skipping
# files whose .srt already exists
any2txt videos/ output/

# Include subdirectories (mirrored under the output directory) and
# re-convert files whose output already exists
any2txt videos/ output/ --recursive --force
```

### Directory mode

When SRC is a directory, every video or audio file found is converted
to `{name}.srt`. Without DST each `.srt` is written next to its source
file; with DST it is written into that directory (mirroring
subdirectories with `--recursive`). Existing outputs are skipped unless
`--force` is given. One failing file does not stop the batch: failures
are summarized at the end and the exit code is 1. Files sharing the
same name but different extensions (e.g. `song.mp3` and `song.mp4`)
conflict on the same output path and are reported as an error.

### Options

| Option              | Default     | Description                                                        |
| ------------------- | ----------- | ------------------------------------------------------------------ |
| `--han`             | `auto`      | Chinese script variant: `auto`, `simplified`, `traditional`        |
| `--line-width`      | `42`        | Max display width per line; full-width chars count as 2            |
| `--max-lines`       | `2`         | Max lines per cue; longer segments split into multiple timed cues  |
| `--model`           | `base`      | Whisper model size (`tiny`, `base`, `small`, `medium`, ...)        |
| `--language`        | auto-detect | ISO language code of the audio (e.g. `zh`)                         |
| `-r`, `--recursive` | off         | Also process files in subdirectories (directory mode)              |
| `-f`, `--force`     | off         | Re-convert files whose output .srt already exists (directory mode)  |
| `--version`         |             | Print the version and exit                                         |

## Notes

- The first run of each model size downloads the model weights
  (the default `base` model is about 150 MB); later runs load from cache.
- Inference runs on CPU with int8 quantization by default.
- Silent stretches are filtered with VAD to avoid hallucinated text;
  media without speech (e.g. music) produces an empty `.srt`.

## Development

This project uses [uv](https://docs.astral.sh/uv/) and
[just](https://github.com/casey/just):

```sh
just install   # set up the dev environment
just check     # run linters and type checks
just test      # run the test suite
just ci        # check + test
```

## License

Copyright (C) 2026 Garrett HE <garrett.he@outlook.com>

MIT License, see [LICENSE](./LICENSE).
