"""
I/O module for nanonispy2.

This module handles binary and ASCII file I/O operations and data format
specifications for reading Nanonis files.
"""

from .binary import BinaryReader
from .formats import DataFormat, FORMAT_REGISTRY

__all__ = [
    'BinaryReader',
    'DataFormat',
    'FORMAT_REGISTRY',
]

