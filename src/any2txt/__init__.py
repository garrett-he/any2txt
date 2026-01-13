"""Extract clean plain text from any documents."""

from importlib.metadata import PackageNotFoundError, version

__version__: str

try:
    __version__ = version('any2txt')
except PackageNotFoundError:
    __version__ = 'unknown'
