"""
nanonispy2 — Python library for reading Nanonis SPM data files.

Primary API
-----------
    Grid  : Read Nanonis grid spectroscopy (.3ds) files.
    Scan  : Read Nanonis scan (.sxm) files.
    Spec  : Read Nanonis point spectroscopy (.dat) files.

Example
-------
    >>> from nanonispy2 import Grid, Scan, Spec
    >>> g = Grid("path/to/file.3ds")
    >>> s = Scan("path/to/file.sxm")
    >>> sp = Spec("path/to/file.dat")

Backward Compatibility
---------------------
    The legacy ``nanonispy2.read`` module still works but will emit
    a FutureWarning. Migrate to ``from nanonispy2 import Grid``.
"""

from .parsers import Grid, Scan, Spec

__all__ = ['Grid', 'Scan', 'Spec']
