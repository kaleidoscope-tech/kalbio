from importlib.metadata import version, PackageNotFoundError

from kalbio.client import KaleidoscopeClient

try:
    __version__ = version("kalbio")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["KaleidoscopeClient"]
