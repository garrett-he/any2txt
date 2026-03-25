# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this project is

A Typer CLI (`any2txt`) that converts media files locally: video/audio
to SRT subtitles (faster-whisper), images to plain text (RapidOCR), and
docx/html/pptx/excel/pdf documents to Markdown (mammoth, markdownify,
python-pptx, openpyxl, PyMuPDF). See README.md for user facing docs;
this file covers things agents need to know.

## Architecture

```text
src/any2txt/
├── cli.py              # argument parsing + pipeline orchestration only
├── assets.py           # AssetSink: dir / drop / embed, chosen by the CLI
├── runtime.py          # packaged-build paths (app dir, models dir); stdlib only
├── zipguard.py         # zip-bomb guard for docx/pptx/xlsx packages
├── asr/                # speech recognition backends
│   ├── base.py         # Segment dataclass: the contract between layers
│   └── faster_whisper.py
├── docx/               # docx to Markdown backend (mammoth)
│   └── mammoth_docx.py # docx -> semantic HTML, assets via the sink
├── excel/              # excel to Markdown backend (openpyxl)
│   └── openpyxl_excel.py # one ## section per sheet, grid as pipe table
├── formats/            # pure text -> text output renderers
│   ├── markdown.py     # shared HTML -> Markdown renderer (markdownify)
│   └── srt.py
├── media/              # input handling, one module per media type
│   ├── audio.py        # extension-based validation only
│   ├── docx.py         # extension-based validation only
│   ├── excel.py        # extension-based validation only
│   ├── html.py         # decoding fallbacks, local image extraction
│   ├── image.py        # extension-based validation only
│   ├── pdf.py          # extension-based validation only
│   ├── pptx.py         # extension-based validation only
│   └── video.py        # extension-based validation only
├── ocr/                # image text recognition backend (RapidOCR)
│   └── rapid_ocr.py
├── pdf/                # pdf to Markdown backend (PyMuPDF)
│   └── pymupdf_pdf.py  # font-size headings, tables, assets via the sink
├── pptx/               # pptx to Markdown backend (python-pptx)
│   └── python_pptx.py  # slides -> sections, assets via the sink
└── text/               # post-processing (han.py: script conversion)
```

Release tooling lives outside the installed package:

```text
packaging/
├── launcher.py         # Nuitka entry point: sys.path + DLL dirs, then cli.app
└── build_release.py    # builds the onefile exe, deps zip, and model zip
```

Design rules:

- `cli.py` must stay thin: parse args, call into subpackages, write output.
- `runtime.py` must remain stdlib-only: the launcher imports it before
  external packages are on `sys.path`, and packaged builds must not
  download models (they resolve `models/<size>` next to the executable).
- Media modules validate/extract; they never format output. New media
  types register their extension predicate in `media/__init__.py`
  (`is_supported`); the conversion pipeline is media-type agnostic and
  must stay that way.
- Format modules consume `Iterable[Segment]` (or plain text) and return
  strings; they never touch the filesystem.
- Document backends (docx/pptx/xlsx/pdf) never write resources either:
  they call `AssetSink.put(name, data, mime)` and use the returned URL,
  dropping the reference when it returns `None`. Only `cli.py` chooses
  the concrete sink (`make_sink`), so `--assets` never leaks into
  backends. `assets.py` owns the caps for `embed` mode.
- Package-based formats call `zipguard.guard_zip` before parsing; the
  size limits must stay conservative.
- The decoding of video/audio happens inside the ASR backend (PyAV via
  faster-whisper). Do not reintroduce an ffmpeg subprocess pipeline.

## Planned extensions (keep the seams clean)

Future media types each get a module under `media/`. New
output formats go under `formats/`. A new ASR engine goes under `asr/`
and must yield `Segment` objects as defined in `asr/base.py`. New OCR
or document-conversion engines go under `ocr/` or a format-named
backend package (backends that are not ASR do not yield `Segment`
objects) and must accept an `AssetSink`. If a change crosses these
layers, stop and reconsider.

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
- Converter tests pass a sink explicitly (`DirSink`, `DropSink`, or
  `DataUriSink`); never construct an output path for them. CLI tests
  use `result.stdout` / `result.stderr` (click 8.5+ separates them) to
  assert the `--stdout` contract; `result.output` is the combined
  stream.

## Gotchas

- Windows is the primary dev environment; paths in commands may use
  backslashes but Python code must stay portable.
- The packaged entry point is `any2txt.cli:app` with a single Typer
  command, so Typer treats it as the root command (no subcommand name).
- `--text-han` uses a StrEnum; `convert_han` takes the enum, not a string.
  It applies to SRT and OCR output, not to document formats.
- Time math in `formats/srt.py` uses display width (full-width = 2);
  `\n` counts as 0. Keep that consistent when editing wrap/split logic.
- Document backends receive an `AssetSink`, not a path. In file mode
  `cli.py` uses `DirSink(assets_dir_for(output))`; on failure it removes
  that directory as well as the output. In `--stdout` mode the default
  sink is `DropSink`, so nothing is written to disk.
- `--stdout` is the machine interface: exactly one input file, text
  only on stdout, all diagnostics on stderr, exit 0/1/2 (2 =
  unsupported input). Never let progress or hints reach stdout.
- docx and html share the HTML-to-Markdown renderer in
  `formats/markdown.py` (a `MarkdownConverter` subclass with table
  support, since markdownify has none natively). `convert_img` drops
  images whose `src` is empty, which is how `drop` mode removes dead
  references. The filesystem part of html conversion (reading local
  images) lives in `media/html.py`, keeping `formats/` pure.
- `read_html` tries UTF-8 (BOM-tolerant), the declared charset, GB18030,
  then lossy UTF-8; keep that order when editing.
- `pdf/pymupdf_pdf.py` infers headings from font sizes (PyMuPDF is
  AGPL-3.0 licensed); heading thresholds live in `_HEADING_RATIOS`.

## Workflow expectations

- Run the linters and the test suite after changes; all checks must
  pass before reporting work as done.
- Verify behavior with a real run only when the user asks for it; model
  downloads are slow and should not happen casually.
