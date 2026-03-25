# any2txt

[![license](https://img.shields.io/badge/license-MIT-blue)](https://github.com/garrett-he/any2txt/blob/main/LICENSE)
[![ci](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml/badge.svg)](https://github.com/garrett-he/any2txt/actions/workflows/ci.yml)

Transcribe video or audio files into SRT subtitles with local speech
recognition (faster-whisper), recognize text in images with local OCR
(RapidOCR), and convert Word documents, HTML pages, and PowerPoint
decks into Markdown (mammoth, markdownify, python-pptx). No API key,
no ffmpeg required.

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
any2txt video.mp4 --text-han simplified

# Pick a bigger model and pin the language
any2txt video.mp4 --asr-model small --asr-language zh

# Custom line width and lines per cue
any2txt video.mp4 --srt-line-width 42 --srt-max-lines 2

# Convert every media file in a directory; each .srt lands next to its source
any2txt videos/

# Convert into an output directory (created if missing), skipping
# files whose .srt already exists
any2txt videos/ output/

# Include subdirectories (mirrored under the output directory) and
# re-convert files whose output already exists
any2txt videos/ output/ --recursive --force

# Recognize text in an image with OCR; writes photo.txt next to the source
any2txt photo.png

# Explicit output path for images (must end with .txt)
any2txt photo.png output.txt

# OCR output also honors --text-han (simplified/traditional Chinese)
any2txt photo.png --text-han simplified

# Convert a Word document to Markdown; writes doc.md next to the source
any2txt doc.docx

# Explicit output path for docx (must end with .md)
any2txt doc.docx output.md

# Convert an HTML page to Markdown; writes page.md next to the source
any2txt page.html

# Convert a PowerPoint deck to Markdown; writes deck.md next to the source
any2txt deck.pptx

# Convert an Excel workbook to Markdown; each sheet becomes a h2 section
any2txt book.xlsx

# Convert a PDF to Markdown; headings are inferred from font sizes
any2txt doc.pdf
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
  paths; OLE objects cannot be located in the document flow, so they
  are listed in an appendix section at the end.
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
