from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("quantalogic-codeact")
except PackageNotFoundError:
    __version__ = "0.1.0"