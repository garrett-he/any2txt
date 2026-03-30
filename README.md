# any2txt

[![license](https://img.shields.io/badge/license-MIT-blue)](https://github.com/garrett-he/any2txt/blob/main/LICENSE)
[![ci](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml/badge.svg)](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml)

Transcribe video or audio files into SRT subtitles with local speech
recognition (faster-whisper), recognize text in images with local OCR
(RapidOCR), and convert Word documents, HTML pages, PowerPoint decks,
Excel workbooks, and PDFs into Markdown (mammoth, markdownify,
python-pptx, openpyxl, PyMuPDF). No API key, no ffmpeg required.

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

Every conversion runs through the `transcribe` subcommand. `--version` is
a root-level option.

```sh
# Write video.srt next to the source file
any2txt transcribe video.mp4

# Audio works the same way
any2txt transcribe song.mp3

# Explicit output path (must end with .srt)
any2txt transcribe video.mp4 output.srt

# Convert the transcript to simplified Chinese
any2txt transcribe video.mp4 --text-han simplified

# Pick a bigger model and pin the language
any2txt transcribe video.mp4 --asr-model small --asr-language zh

# Custom line width and lines per cue
any2txt transcribe video.mp4 --srt-line-width 42 --srt-max-lines 2

# Convert every media file in a directory; each .srt lands next to its source
any2txt transcribe videos/

# Convert into an output directory (created if missing), skipping
# files whose .srt already exists
any2txt transcribe videos/ output/

# Include subdirectories (mirrored under the output directory) and
# re-convert files whose output already exists
any2txt transcribe videos/ output/ --recursive --force

# Recognize text in an image with OCR; writes photo.txt next to the source
any2txt transcribe photo.png

# Explicit output path for images (must end with .txt)
any2txt transcribe photo.png output.txt

# OCR output also honors --text-han (simplified/traditional Chinese)
any2txt transcribe photo.png --text-han simplified

# Convert a Word document to Markdown; writes doc.md next to the source
any2txt transcribe doc.docx

# Explicit output path for docx (must end with .md)
any2txt transcribe doc.docx output.md

# Convert an HTML page to Markdown; writes page.md next to the source
any2txt transcribe page.html

# Convert a PowerPoint deck to Markdown; writes deck.md next to the source
any2txt transcribe deck.pptx

# Convert an Excel workbook to Markdown; each sheet becomes a h2 section
any2txt transcribe book.xlsx

# Convert a PDF to Markdown; headings are inferred from font sizes
any2txt transcribe doc.pdf

# Machine interface: write one file's text to stdout, no output file
any2txt transcribe doc.pdf --stdout

# Inline extracted images as data URIs (self-contained Markdown)
any2txt transcribe doc.docx --stdout --assets embed

# Omit extracted images and attachments entirely
any2txt transcribe doc.docx --assets drop
```

### Directory mode

When SRC is a directory, every supported media file found is converted:
video and audio files become `{name}.srt`, images become `{name}.txt`,
and Word documents, HTML pages, PowerPoint decks, Excel workbooks, and
PDFs become `{name}.md`. Without DST each output is written next to
its source file; with DST it is written into that directory (mirroring
subdirectories with `--recursive`). Existing outputs are skipped unless
`--force` is given. One failing file does not stop the batch: failures
are summarized at the end and the exit code is 1. Files sharing the
same name but different extensions (e.g. `song.mp3` and `song.mp4`)
conflict on the same output path and are reported as an error.

### Machine interface (`--stdout`)

`--stdout` is intended for programs that call any2txt directly. It
accepts a single file (not a directory), writes the extracted text to
stdout, and writes no output file. Diagnostics, progress, and warnings
always go to stderr, so stdout contains only the payload. Output is
always UTF-8; a single trailing newline is added when the text is not
empty, and an empty conversion writes nothing at all.

Exit codes: `0` success, `1` failure (missing input, I/O or conversion
error), `2` unsupported input type.

Extracted resources are controlled by `--assets`:

| Value   | Behavior                                                              |
| ------- | --------------------------------------------------------------------- |
| `dir`   | Write into `{name}_files/` next to the output (file mode default)     |
| `drop`  | Omit images and attachments; no files are written (stdout default)    |
| `embed` | Inline images as `data:` URIs; no files are written                   |

`--assets dir` requires an output file, so it cannot be combined with
`--stdout`. In `drop` mode references are removed instead of leaving
dead links. `embed` only inlines renderable image types (PNG, JPEG,
GIF, WebP, SVG) up to 2 MiB per image and 16 MiB in total; anything
else is dropped. Note that GitHub and some Markdown renderers strip
`data:` image URIs, so `embed` is best for local viewing and ingestion
pipelines that support them.

### Options

| Option              | Default     | Description                                                        |
| ------------------- | ----------- | ------------------------------------------------------------------ |
| `--text-han`        | `auto`      | Chinese script variant: `auto`, `simplified`, `traditional`        |
| `--srt-line-width`  | `42`        | Max display width per line; full-width chars count as 2            |
| `--srt-max-lines`   | `2`         | Max lines per cue; longer segments split into multiple timed cues  |
| `--asr-model`       | `base`      | Whisper model size (`tiny`, `base`, `small`, `medium`, ...)        |
| `--asr-language`    | auto-detect | ISO language code of the audio (e.g. `zh`)                         |
| `-r`, `--recursive` | off         | Also process files in subdirectories (directory mode)              |
| `-f`, `--force`     | off         | Re-convert files whose output already exists (directory mode)       |
| `--stdout`          | off         | Write one file's text to stdout instead of a file                   |
| `--assets`          | `dir`       | Extracted resources: `dir`, `drop`, or `embed` (`drop` with stdout) |
| `--version`         |             | Print the version and exit                                         |

## Notes

- The first run of each model size downloads the model weights
  (the default `base` model is about 150 MB); later runs load from cache.
- Inference runs on CPU with int8 quantization by default.
- Silent stretches are filtered with VAD to avoid hallucinated text;
  media without speech (e.g. music) produces an empty `.srt`.
- Image OCR uses RapidOCR with the bundled PP-OCRv6 Chinese/English
  models (ONNX Runtime backend); no model download is required.
- OCR output lists each detected text block on its own line, ordered
  top-to-bottom; images without detectable text produce an empty `.txt`.
- docx conversion keeps the document's semantic structure (headings,
  emphasis, lists, links, tables); visual styling (fonts, colors, sizes)
  is not preserved. `--text-han` is not applied to docx output.
- Embedded images and OLE objects are extracted into a `{name}_files/`
  directory next to the output Markdown and referenced with relative
  paths (see `--assets` to drop or embed them instead); OLE objects
  cannot be located in the document flow, so they are listed in an
  appendix section at the end.
- HTML pages are decoded as UTF-8 (with optional BOM), then by their
  declared charset, then as GB18030, and finally with lossy UTF-8, so
  legacy Chinese pages convert without failing.
- HTML conversion renders the page structure to Markdown with the same
  engine as docx conversion (including tables). Images referenced by
  local paths are copied into the `{name}_files/` directory next to the
  output and referenced with relative paths; remote URLs, data URIs,
  and missing files are left untouched. `--text-han` is not applied to
  docx/html output.
- PowerPoint conversion renders each slide as a `##` section: the slide
  title becomes the heading, body placeholders become bullet lists,
  tables become Markdown tables, speaker notes become blockquotes, and
  pictures are extracted into the `{name}_files/` directory like docx.
  `--text-han` is not applied to pptx output.
- Excel conversion renders each non-empty sheet as a `## {sheet name}`
  section with its grid as a Markdown table (first row is the header).
  Merged cells repeat their top-left value on every row, and embedded
  pictures are extracted into the `{name}_files/` directory and
  referenced inside their anchored cell. Formula cells show their last
  computed value. `--text-han` is not applied to excel output.
- PDF conversion infers headings from font sizes (body size is the
  document-wide dominant size), renders ruled tables as Markdown
  tables, extracts pictures into the `{name}_files/` directory, and
  turns URI links into Markdown links. `--text-han` is not applied to pdf
  output. PyMuPDF is licensed under AGPL-3.0; local personal use is
  unaffected, but distributing this tool imposes AGPL obligations.
- Office documents and workbooks are zip packages; entries whose
  declared uncompressed size exceeds 512 MiB, or 1 GiB in total, are
  rejected before decompression (zip-bomb protection).

## Development

This project uses [uv](https://docs.astral.sh/uv/) and
[just](https://github.com/casey/just):

```sh
just install   # set up the dev environment
just check     # run linters and type checks
just test      # run the test suite
just ci        # check + test
```

## Packaging

`just release` builds three Windows x64 artifacts under `dist/release/`:

- `any2txt-<version>-win-x64.exe` — a Nuitka onefile executable that
  contains only `any2txt` and the Python runtime.
- `any2txt-<version>-deps-win-x64.zip` — the third-party dependencies;
  extract it so that `lib/site-packages/` sits next to the executable.
- `any2txt-<version>-models.zip` — the `base` Whisper model; extract it
  so that `models/base/` sits next to the executable.

The deployed layout is:

```text
any2txt/
├── any2txt.exe
├── lib/site-packages/
└── models/base/
```

The executable exits with an error when `lib/site-packages/` is missing.
Packaged builds load models from `models/<size>/` and never download
them; set `ANY2TXT_MODELS` to use a different model directory.

## License

Copyright (C) 2026 Garrett HE <garrett.he@outlook.com>

MIT License, see [LICENSE](./LICENSE).
