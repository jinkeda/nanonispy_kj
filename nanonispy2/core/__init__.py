"""
Core module for nanonispy2.

This module contains base classes, exceptions, and validation utilities
used throughout the nanonispy2 package.
"""

from .base import NanonisFile
from .exceptions import (
    UnhandledFileError,
    FileHeaderNotFoundError,
    InvalidDataFormatError,
    ValidationError,
)
from .validators import (
    validate_file_path,
    validate_dimensions,
    validate_data_format,
    validate_header_entries,
)

__all__ = [
    'NanonisFile',
    'UnhandledFileError',
    'FileHeaderNotFoundError',
    'InvalidDataFormatError',
    'ValidationError',
    'validate_file_path',
    'validate_dimensions',
    'validate_data_format',
    'validate_header_entries',
]

