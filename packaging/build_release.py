"""Build the three release artifacts for any2txt.

The executable is a Nuitka onefile binary that contains only the
any2txt package and the Python runtime; third-party dependencies and
the Whisper model are shipped separately and extracted next to it:

- ``any2txt-<version>-win-x64.exe``
- ``any2txt-<version>-deps-win-x64.zip`` (``lib/site-packages``)
- ``any2txt-<version>-models.zip`` (``models/base``)

Intermediates live under ``dist/app`` so the executable can be smoke
tested with its external packages before the archives are created.
"""

import argparse
import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
MODEL_REPO = 'Systran/faster-whisper-base'
MODEL_PATTERNS = ['config.json', 'preprocessor_config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*']

# Standard-library modules that are never needed by the external packages
# and would only bloat the executable.
_STDLIB_EXCLUDES = frozenset(
    {
        'antigravity',
        'distutils',
        'ensurepip',
        'idlelib',
        'lib2to3',
        'test',
        'this',
        'tkinter',
        'turtle',
        'turtledemo',
        'unittest',
        'venv',
    }
)


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    """Run one build command, echoing it first."""
    print('+', ' '.join(command))
    subprocess.run(command, cwd=ROOT, check=True, env=env)


def _import_names() -> list[str]:
    """Return top-level import names of every installed distribution except any2txt."""
    return sorted(name for name in importlib.metadata.packages_distributions() if name != 'any2txt')


def _stdlib_options() -> list[str]:
    """Return Nuitka options that bundle the standard library.

    External packages import standard-library modules that Nuitka cannot
    see while compiling, so those modules must be included explicitly.
    """
    options: list[str] = []
    for name in sorted(sys.stdlib_module_names):
        if name in _STDLIB_EXCLUDES or name.startswith('_test'):
            continue
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            continue
        if spec is None or spec.origin in (None, 'built-in', 'frozen'):
            continue
        option = 'include-package' if spec.submodule_search_locations is not None else 'include-module'
        options.append(f'--{option}={name}')
    return options


def _python3_dll() -> Path:
    """Return python3.dll, the stable-ABI shim that binary wheels link against.

    Nuitka bundles only the versioned runtime (python313.dll), so abi3
    extensions such as tokenizers fail to load without this shim.
    """
    for candidate in (Path(sys.base_prefix) / 'python3.dll', Path(sys.executable).parents[1] / 'python3.dll'):
        if candidate.is_file():
            return candidate
    raise RuntimeError('python3.dll not found in the Python installation')


def _build_exe(dist: Path) -> Path:
    """Compile the onefile executable with every third-party import left external."""
    output = dist / 'nuitka'
    shutil.rmtree(output, ignore_errors=True)
    command = [
        sys.executable,
        '-m',
        'nuitka',
        str(ROOT / 'packaging' / 'launcher.py'),
        '--onefile',
        '--assume-yes-for-downloads',
        '--include-package=any2txt',
        '--no-deployment-flag=excluded-module-usage',
        f'--include-data-files={_python3_dll()}=python3.dll',
        f'--output-dir={output}',
        '--output-filename=any2txt.exe',
    ]
    command += [f'--nofollow-import-to={name}' for name in _import_names()]
    command += _stdlib_options()
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
    _run(command, env=env)
    return output / 'any2txt.exe'


def _build_deps(app: Path) -> Path:
    """Install the runtime dependencies into the app's lib/site-packages."""
    requirements = app.parent / 'requirements-runtime.txt'
    _run(
        [
            'uv',
            'export',
            '--no-dev',
            '--no-emit-project',
            '--format',
            'requirements.txt',
            '--output-file',
            str(requirements),
        ]
    )
    lib_root = app / 'lib'
    shutil.rmtree(lib_root, ignore_errors=True)
    lib = lib_root / 'site-packages'
    lib.mkdir(parents=True)
    _run(['uv', 'pip', 'install', '--target', str(lib), '--python', sys.executable, '-r', str(requirements)])
    dist_info = lib / f'any2txt-{VERSION}.dist-info'
    dist_info.mkdir()
    (dist_info / 'METADATA').write_text(
        f'Metadata-Version: 2.1\nName: any2txt\nVersion: {VERSION}\n',
        encoding='utf-8',
    )
    _prune(lib)
    return lib


def _prune(lib: Path) -> None:
    """Remove bytecode caches and the uv install marker before archiving.

    The smoke test imports the external packages and recreates
    ``__pycache__`` directories, so this runs again right before zipping.
    """
    for cache in lib.rglob('__pycache__'):
        shutil.rmtree(cache, ignore_errors=True)
    for compiled in lib.rglob('*.pyc'):
        compiled.unlink(missing_ok=True)
    (lib / '.lock').unlink(missing_ok=True)


def _build_model(app: Path) -> Path:
    """Copy the base Whisper model into the app's models directory."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    models = app / 'models'
    shutil.rmtree(models, ignore_errors=True)
    target = models / 'base'
    target.mkdir(parents=True)
    try:
        source = Path(snapshot_download(MODEL_REPO, allow_patterns=MODEL_PATTERNS, local_files_only=True))
    except LocalEntryNotFoundError:
        source = Path(snapshot_download(MODEL_REPO, allow_patterns=MODEL_PATTERNS))
    for pattern in MODEL_PATTERNS:
        for path in source.glob(pattern):
            shutil.copy2(path, target / path.name)
    if not (target / 'model.bin').is_file():
        raise RuntimeError(f'model.bin is missing from {source}')
    return models


def _smoke_test(app: Path) -> None:
    """Check that the executable finds its external packages."""
    env = dict(os.environ, ANY2TXT_DEBUG_PATHS='1')
    _run([str(app / 'any2txt.exe'), '--version'], env=env)


def _zip_tree(source: Path, name: str, release: Path) -> Path:
    """Zip one tree (lib or models), keeping its top-level directory name."""
    archive = release / name
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(source.rglob('*')):
            bundle.write(path, (Path(source.name) / path.relative_to(source)).as_posix())
    return archive


def main() -> int:
    """Build the executable, the dependency archive, and the model archive."""
    if os.name != 'nt':
        print('error: release artifacts are only built on Windows', file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description='Build the any2txt release artifacts.')
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    parser.add_argument('--skip-exe', action='store_true')
    parser.add_argument('--skip-deps', action='store_true')
    parser.add_argument('--skip-model', action='store_true')
    args = parser.parse_args()

    dist = args.dist.resolve()
    app = dist / 'app'
    release = dist / 'release'
    app.mkdir(parents=True, exist_ok=True)
    release.mkdir(parents=True, exist_ok=True)

    executable = dist / 'nuitka' / 'any2txt.exe'
    if not args.skip_exe:
        executable = _build_exe(dist)
    shutil.copy2(executable, app / 'any2txt.exe')
    if not args.skip_deps:
        _build_deps(app)
    if not args.skip_model:
        _build_model(app)
    _smoke_test(app)
    _prune(app / 'lib' / 'site-packages')

    artifacts = [
        release / f'any2txt-{VERSION}-win-x64.exe',
        _zip_tree(app / 'lib', f'any2txt-{VERSION}-deps-win-x64.zip', release),
        _zip_tree(app / 'models', f'any2txt-{VERSION}-models.zip', release),
    ]
    shutil.copy2(app / 'any2txt.exe', artifacts[0])
    for artifact in artifacts:
        print(f'{artifact} ({artifact.stat().st_size / 1024 / 1024:.1f} MiB)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
