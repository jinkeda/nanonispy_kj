"""
Legacy backward-compatibility shim for nanonispy2.read.

.. deprecated::
    Import directly from ``nanonispy2`` instead::

        from nanonispy2 import Grid, Scan, Spec

    This module will be removed in a future version.
"""

import warnings

# Re-export classes from new modular locations
from .parsers.grid import Grid
from .parsers.scan import Scan
from .parsers.spec import Spec
from .core.exceptions import UnhandledFileError, FileHeaderNotFoundError

# Re-export topo resolver for backward compat with tests
from .parsers.grid import _resolve_topo_index

# Emit deprecation warning on import
warnings.warn(
    "nanonispy2.read is deprecated. Import directly from nanonispy2: "
    "from nanonispy2 import Grid, Scan, Spec",
    FutureWarning,
    stacklevel=2
)

__all__ = ['Grid', 'Scan', 'Spec', 'UnhandledFileError', 'FileHeaderNotFoundError']
