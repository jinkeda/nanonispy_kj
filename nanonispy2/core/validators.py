"""
Validation utilities for nanonispy2.

This module provides functions to validate input data, file paths, dimensions,
and other parameters to ensure data integrity and proper error handling.
"""

import os
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .exceptions import (
    ValidationError,
    InvalidDataFormatError,
    DimensionMismatchError,
    MissingHeaderEntryError,
)


def validate_file_path(file_path: str, required_extension: Optional[str] = None) -> str:
    """
    Validate that a file path exists and has the correct extension.

    Parameters
    ----------
    file_path : str
        Path to the file to validate.
    required_extension : str, optional
        Required file extension (e.g., '3ds', 'sxm', 'dat').
        If None, only existence is checked.

    Returns
    -------
    str
        Absolute path to the validated file.

    Raises
    ------
    ValidationError
        If the file does not exist or has the wrong extension.
    """
    if not os.path.exists(file_path):
        raise ValidationError(f"File does not exist: {file_path}")

    if not os.path.isfile(file_path):
        raise ValidationError(f"Path is not a file: {file_path}")

    if required_extension is not None:
        _, ext = os.path.splitext(file_path)
        ext = ext.lstrip('.')
        if ext != required_extension:
            raise ValidationError(
                f"Expected file extension '.{required_extension}', got '.{ext}'"
            )

    return os.path.abspath(file_path)


def validate_dimensions(
    data_shape: Tuple[int, ...],
    expected_dims: Optional[int] = None,
    expected_shape: Optional[Tuple[int, ...]] = None,
    allow_partial_match: bool = False
) -> bool:
    """
    Validate that data has the expected dimensions.

    Parameters
    ----------
    data_shape : tuple of int
        Shape of the data array.
    expected_dims : int, optional
        Expected number of dimensions.
    expected_shape : tuple of int, optional
        Expected shape. Use None for dimensions that can vary.
    allow_partial_match : bool, default False
        If True, only check leading dimensions when expected_shape is provided.

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    DimensionMismatchError
        If dimensions do not match expectations.
    """
    if expected_dims is not None:
        if len(data_shape) != expected_dims:
            raise DimensionMismatchError(
                f"Expected {expected_dims} dimensions, got {len(data_shape)}"
            )

    if expected_shape is not None:
        if allow_partial_match:
            check_dims = min(len(data_shape), len(expected_shape))
            data_check = data_shape[:check_dims]
            expected_check = expected_shape[:check_dims]
        else:
            if len(data_shape) != len(expected_shape):
                raise DimensionMismatchError(
                    f"Shape mismatch: expected {expected_shape}, got {data_shape}"
                )
            data_check = data_shape
            expected_check = expected_shape

        for i, (actual, expected) in enumerate(zip(data_check, expected_check)):
            if expected is not None and actual != expected:
                raise DimensionMismatchError(
                    f"Dimension {i} mismatch: expected {expected}, got {actual}"
                )

    return True


def validate_data_format(data_format: str, valid_formats: Optional[List[str]] = None) -> str:
    """
    Validate that a data format specification is valid.

    Parameters
    ----------
    data_format : str
        Data format string (e.g., '>f4', '<f8').
    valid_formats : list of str, optional
        List of valid format strings. If None, checks numpy dtype validity.

    Returns
    -------
    str
        Validated data format string.

    Raises
    ------
    InvalidDataFormatError
        If the data format is invalid.
    """
    if valid_formats is not None:
        if data_format not in valid_formats:
            raise InvalidDataFormatError(
                f"Invalid data format '{data_format}'. "
                f"Valid formats: {', '.join(valid_formats)}"
            )
    else:
        # Check if numpy recognizes the dtype
        try:
            np.dtype(data_format)
        except TypeError as e:
            raise InvalidDataFormatError(
                f"Invalid numpy dtype specification '{data_format}': {e}"
            )

    return data_format


def validate_header_entries(
    header: Dict[str, Any],
    required_keys: List[str],
    optional_keys: Optional[List[str]] = None
) -> bool:
    """
    Validate that a header dictionary contains all required entries.

    Parameters
    ----------
    header : dict
        Header dictionary to validate.
    required_keys : list of str
        List of required header keys.
    optional_keys : list of str, optional
        List of optional header keys for reference.

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    MissingHeaderEntryError
        If any required keys are missing.
    ValidationError
        If the header is not a dictionary.
    """
    if not isinstance(header, dict):
        raise ValidationError("Header must be a dictionary")

    missing_keys = [key for key in required_keys if key not in header]

    if missing_keys:
        raise MissingHeaderEntryError(
            f"Missing required header entries: {', '.join(missing_keys)}"
        )

    return True


def validate_array_size(
    array: np.ndarray,
    expected_size: int,
    array_name: str = "array"
) -> bool:
    """
    Validate that an array has the expected total size.

    Parameters
    ----------
    array : numpy.ndarray
        Array to validate.
    expected_size : int
        Expected total number of elements.
    array_name : str, default "array"
        Name of the array for error messages.

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    DimensionMismatchError
        If array size does not match expectation.
    """
    if array.size != expected_size:
        raise DimensionMismatchError(
            f"{array_name} has {array.size} elements, expected {expected_size}"
        )

    return True


def validate_numeric_range(
    value: Union[int, float],
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    value_name: str = "value"
) -> bool:
    """
    Validate that a numeric value is within a specified range.

    Parameters
    ----------
    value : int or float
        Value to validate.
    min_value : int or float, optional
        Minimum allowed value (inclusive).
    max_value : int or float, optional
        Maximum allowed value (inclusive).
    value_name : str, default "value"
        Name of the value for error messages.

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    ValidationError
        If value is outside the specified range.
    """
    if min_value is not None and value < min_value:
        raise ValidationError(
            f"{value_name} ({value}) is less than minimum ({min_value})"
        )

    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{value_name} ({value}) is greater than maximum ({max_value})"
        )

    return True


def validate_positive_integers(
    values: Dict[str, int],
    allow_zero: bool = False
) -> bool:
    """
    Validate that a dictionary of values contains positive integers.

    Parameters
    ----------
    values : dict
        Dictionary mapping names to integer values.
    allow_zero : bool, default False
        If True, zero is considered valid.

    Returns
    -------
    bool
        True if validation passes.

    Raises
    ------
    ValidationError
        If any value is not a positive integer.
    """
    min_value = 0 if allow_zero else 1

    for name, value in values.items():
        if not isinstance(value, (int, np.integer)):
            raise ValidationError(f"{name} must be an integer, got {type(value)}")

        if value < min_value:
            raise ValidationError(
                f"{name} must be >= {min_value}, got {value}"
            )

    return True

