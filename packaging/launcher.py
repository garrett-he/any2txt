"""Nuitka entry point that loads external packages before the CLI.

The executable ships without third-party dependencies; they live in
``lib/site-packages`` next to the executable. This launcher puts that
directory on ``sys.path`` and registers the directories holding DLLs
required by compiled dependencies, then hands control to the CLI.
"""

import os
import sys
from pathlib import Path

_DLL_SUBDIRS = (
    'onnxruntime/capi',
    'ctranslate2',
    'pymupdf',
    'av.libs',
    'numpy.libs',
    'shapely.libs',
    'cv2',
)

_dll_handles: list[object] = []


def _prepare(app_dir: Path) -> None:
    """Put the external site-packages on sys.path and register DLL directories."""
    lib = app_dir / 'lib' / 'site-packages'
    if not lib.is_dir():
        sys.exit(f'any2txt: external packages not found at {lib}')
    sys.path.insert(0, str(lib))
    if os.name == 'nt':
        for sub in _DLL_SUBDIRS:
            directory = lib / sub
            if directory.is_dir():
                _dll_handles.append(os.add_dll_directory(str(directory)))
    if os.environ.get('ANY2TXT_DEBUG_PATHS'):
        print(f'app dir: {app_dir}', file=sys.stderr)


def main() -> None:
    """Prepare the runtime and run the CLI."""
    _prepare(Path(sys.argv[0]).resolve().parent)
    from any2txt.cli import app

    app()


if __name__ == '__main__':
    main()
