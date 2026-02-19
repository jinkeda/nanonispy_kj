"""
Validation utilities for nanonispy2.

This module provides functions to validate input data, file paths,
and header entries to ensure data integrity and proper error handling.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import (
    ValidationError,
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
    path = Path(file_path)

    if not path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    if not path.is_file():
        raise ValidationError(f"Path is not a file: {file_path}")

    if required_extension is not None:
        ext = path.suffix.lstrip('.')
        if ext != required_extension:
            raise ValidationError(
                f"Expected file extension '.{required_extension}', got '.{path.suffix}'"
            )

    return str(path.resolve())


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
