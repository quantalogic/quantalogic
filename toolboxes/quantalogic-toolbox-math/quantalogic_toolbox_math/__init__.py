from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from quantalogic_toolbox_math.tools import (
    symbolic_diff,
    symbolic_integrate,
    symbolic_matrix,
    symbolic_ode,
    symbolic_series,
    symbolic_simplify,
    symbolic_solve,
)

try:
    __version__ = _version("quantalogic-toolbox-math")
except PackageNotFoundError:
    __version__ = "0.16.0"

__all__ = [
    "symbolic_simplify",
    "symbolic_solve",
    "symbolic_diff",
    "symbolic_integrate",
    "symbolic_series",
    "symbolic_matrix",
    "symbolic_ode"
]

def get_tools():
    return [
        symbolic_simplify,
        symbolic_solve,
        symbolic_diff,
        symbolic_integrate,
        symbolic_series,
        symbolic_matrix,
        symbolic_ode
    ]