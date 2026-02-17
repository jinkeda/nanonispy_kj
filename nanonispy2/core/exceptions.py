"""
Custom exceptions for nanonispy2.

This module defines all custom exception classes used throughout the package
to provide clear and specific error messages for different failure scenarios.
"""


class NanonisError(Exception):
    """Base exception class for all nanonispy2 errors."""
    pass


class UnhandledFileError(NanonisError):
    """
    Raised when an unsupported file type is encountered.

    This exception is raised when attempting to parse a file with an
    unrecognized extension or format.
    """
    pass


class FileHeaderNotFoundError(NanonisError):
    """
    Raised when the file header cannot be located.

    This exception is raised when the expected header end tag is not found
    in the file, indicating a corrupted or invalid file format.
    """
    pass


class InvalidDataFormatError(NanonisError):
    """
    Raised when an invalid data format specification is provided.

    This exception is raised when attempting to use a data format that is
    not supported or incorrectly specified.
    """
    pass


class ValidationError(NanonisError):
    """
    Raised when data validation fails.

    This exception is raised when input data does not meet expected
    constraints or requirements.
    """
    pass


class CorruptedDataError(NanonisError):
    """
    Raised when data appears to be corrupted.

    This exception is raised when data cannot be properly parsed or contains
    inconsistencies that suggest corruption.
    """
    pass


class MissingHeaderEntryError(NanonisError):
    """
    Raised when a required header entry is missing.

    This exception is raised when parsing a header that lacks required
    fields for proper data interpretation.
    """
    pass


class InvalidHeaderValueError(NanonisError):
    """
    Raised when a header entry contains an invalid value.

    This exception is raised when a header value cannot be parsed or
    does not meet expected format requirements.
    """
    pass


class IncompleteScanError(NanonisError):
    """
    Raised when attempting to load an incomplete scan.

    This exception is raised when a scan file does not contain the expected
    amount of data, indicating the scan was not completed.
    """
    pass


class DimensionMismatchError(NanonisError):
    """
    Raised when data dimensions do not match expected values.

    This exception is raised when attempting to reshape or process data
    with incompatible dimensions.
    """
    pass

