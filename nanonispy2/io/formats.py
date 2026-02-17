"""
Data format definitions for nanonispy2.

This module defines supported data formats and provides utilities for
format validation and conversion.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np

from ..core.exceptions import InvalidDataFormatError
from ..core.validators import validate_data_format


@dataclass
class DataFormat:
    """
    Data format specification for binary data reading.

    Attributes
    ----------
    name : str
        Human-readable name for the format.
    dtype : str
        NumPy dtype string (e.g., '>f4', '<f8').
    description : str
        Description of the format.
    byte_size : int
        Number of bytes per value.
    """
    name: str
    dtype: str
    description: str
    byte_size: int

    def __post_init__(self):
        """Validate dtype specification after initialization."""
        try:
            np.dtype(self.dtype)
        except TypeError as e:
            raise InvalidDataFormatError(
                f"Invalid dtype '{self.dtype}' for format '{self.name}': {e}"
            )


# Registry of supported data formats
FORMAT_REGISTRY: Dict[str, DataFormat] = {
    'big endian float 32': DataFormat(
        name='big endian float 32',
        dtype='>f4',
        description='Big-endian 32-bit floating point',
        byte_size=4
    ),
    'little endian float 32': DataFormat(
        name='little endian float 32',
        dtype='<f4',
        description='Little-endian 32-bit floating point',
        byte_size=4
    ),
    'big endian float 64': DataFormat(
        name='big endian float 64',
        dtype='>f8',
        description='Big-endian 64-bit floating point',
        byte_size=8
    ),
    'little endian float 64': DataFormat(
        name='little endian float 64',
        dtype='<f8',
        description='Little-endian 64-bit floating point',
        byte_size=8
    ),
    'big endian int 16': DataFormat(
        name='big endian int 16',
        dtype='>i2',
        description='Big-endian 16-bit signed integer',
        byte_size=2
    ),
    'little endian int 16': DataFormat(
        name='little endian int 16',
        dtype='<i2',
        description='Little-endian 16-bit signed integer',
        byte_size=2
    ),
    'big endian int 32': DataFormat(
        name='big endian int 32',
        dtype='>i4',
        description='Big-endian 32-bit signed integer',
        byte_size=4
    ),
    'little endian int 32': DataFormat(
        name='little endian int 32',
        dtype='<i4',
        description='Little-endian 32-bit signed integer',
        byte_size=4
    ),
}


# Default format for Nanonis files
DEFAULT_FORMAT = 'big endian float 32'


def get_format(format_name: Optional[str] = None) -> DataFormat:
    """
    Get a data format specification by name.

    Parameters
    ----------
    format_name : str, optional
        Name of the format. If None, returns default format.

    Returns
    -------
    DataFormat
        Data format specification object.

    Raises
    ------
    InvalidDataFormatError
        If format name is not recognized.
    """
    if format_name is None:
        format_name = DEFAULT_FORMAT

    if format_name not in FORMAT_REGISTRY:
        raise InvalidDataFormatError(
            f"Unknown format '{format_name}'. "
            f"Available formats: {', '.join(FORMAT_REGISTRY.keys())}"
        )

    return FORMAT_REGISTRY[format_name]


def get_dtype(format_name: Optional[str] = None) -> str:
    """
    Get NumPy dtype string for a format name.

    Parameters
    ----------
    format_name : str, optional
        Name of the format. If None, returns default dtype.

    Returns
    -------
    str
        NumPy dtype string.
    """
    return get_format(format_name).dtype


def register_custom_format(
    name: str,
    dtype: str,
    description: str,
    byte_size: int
) -> DataFormat:
    """
    Register a custom data format.

    Parameters
    ----------
    name : str
        Name for the custom format.
    dtype : str
        NumPy dtype string.
    description : str
        Description of the format.
    byte_size : int
        Number of bytes per value.

    Returns
    -------
    DataFormat
        The registered data format object.

    Raises
    ------
    InvalidDataFormatError
        If dtype is invalid or name already exists.
    """
    if name in FORMAT_REGISTRY:
        raise InvalidDataFormatError(
            f"Format name '{name}' is already registered. "
            "Choose a different name or unregister the existing format first."
        )

    # Validate dtype
    validate_data_format(dtype)

    # Create and register format
    custom_format = DataFormat(
        name=name,
        dtype=dtype,
        description=description,
        byte_size=byte_size
    )

    FORMAT_REGISTRY[name] = custom_format

    return custom_format


def list_available_formats() -> Dict[str, str]:
    """
    List all available data formats.

    Returns
    -------
    dict
        Dictionary mapping format names to descriptions.
    """
    return {
        name: fmt.description
        for name, fmt in FORMAT_REGISTRY.items()
    }


def validate_format_compatibility(
    format_name: str,
    expected_byte_size: Optional[int] = None
) -> bool:
    """
    Validate that a format is compatible with expected constraints.

    Parameters
    ----------
    format_name : str
        Name of the format to validate.
    expected_byte_size : int, optional
        Expected byte size per value.

    Returns
    -------
    bool
        True if format is compatible.

    Raises
    ------
    InvalidDataFormatError
        If format is not compatible.
    """
    fmt = get_format(format_name)

    if expected_byte_size is not None:
        if fmt.byte_size != expected_byte_size:
            raise InvalidDataFormatError(
                f"Format '{format_name}' has byte size {fmt.byte_size}, "
                f"expected {expected_byte_size}"
            )

    return True

