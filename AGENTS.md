# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

A Typer CLI (`any2txt`) that transcribes the audio track of a video file
into SRT subtitles using faster-whisper locally. See README.md for user
facing docs; this file covers things agents need to know.

## Architecture

```text
src/any2txt/
├── cli.py              # argument parsing + pipeline orchestration only
├── asr/                # speech recognition backends
│   ├── base.py         # Segment dataclass: the contract between layers
│   └── faster_whisper.py
├── formats/            # output renderers (currently SRT only)
│   └── srt.py
├── media/              # input handling, one module per media type
│   ├── audio.py        # extension-based validation only
│   └── video.py        # extension-based validation only
└── text/               # post-processing (han.py: script conversion)
```

Design rules:

- `cli.py` must stay thin: parse args, call into subpackages, write output.
- Media modules validate/extract; they never format output. New media
  types register their extension predicate in `media/__init__.py`
  (`is_supported`); the conversion pipeline is media-type agnostic and
  must stay that way.
- Format modules consume `Iterable[Segment]` (or plain text) and return
  strings; they never touch the filesystem.
- The decoding of video/audio happens inside the ASR backend (PyAV via
  faster-whisper). Do not reintroduce an ffmpeg subprocess pipeline.

## Planned extensions (keep the seams clean)

Future media types (audio, pdf, image) each get a module under
`media/`. New output formats go under `formats/`. A new ASR engine goes
under `asr/` and must yield `Segment` objects as defined in
`asr/base.py`. If a change crosses these layers, stop and reconsider.

## Toolchain and conventions

- Package manager is uv; task runner is just. Never edit `uv.lock` by
  hand; add dependencies with `uv add`.
- Python >= 3.12 (StrEnum, `X | None` unions are fine; no `typing.Optional`).
- Ruff: single quotes, 120 columns, Google-style docstrings on every
  module, class, and function (pydocstyle D rules are enforced).
- pyrefly runs in strict mode: every function needs full type
  annotations, no untyped imports, no implicit-any lambdas. Prefer
  small named functions over lambdas in tests.
- pytest config lives under `[tool.pytest]` in pyproject.toml (pytest 9
  style with dotted `ini_options.*` keys). pyproject-fmt re-sorts TOML
  keys; run it instead of hand-tuning formatting.
- `RUF001` is per-file ignored in `formats/srt.py` and
  `tests/test_srt.py` because CJK punctuation strings there are
  intentional.
- `av<16` is pinned on purpose: faster-whisper passes
  `metadata_errors` to `av.open()`, which av 16+ removed. Removing the
  pin breaks transcription at runtime.

## Testing patterns

- Tests must not require ffmpeg, network, or real model weights.
  Stub `transcribe` via `monkeypatch.setattr('any2txt.cli.transcribe',
...)`; note the stub target is the `cli` namespace because cli.py
  imports names directly.
- Stub callables in tests must be named functions with full
  annotations (strict type checking rejects unannotated lambdas).
- Coverage gate is 80% (`fail_under` in pyproject.toml). Format
  functions are pure: test edge cases (empty input, zero-duration
  segments, width boundaries) directly without CLI plumbing.

## Gotchas

- Windows is the primary dev environment; paths in commands may use
  backslashes but Python code must stay portable.
- The packaged entry point is `any2txt.cli:app` with a single Typer
  command, so Typer treats it as the root command (no subcommand name).
- `--han` uses a StrEnum; `convert_han` takes the enum, not a string.
- Time math in `formats/srt.py` uses display width (full-width = 2);
  `\n` counts as 0. Keep that consistent when editing wrap/split logic.

## Workflow expectations

- Run the linters and the test suite after changes; all checks must
  pass before reporting work as done.
- Verify behavior with a real run only when the user asks for it; model
  downloads are slow and should not happen casually.
