"""
Binary file reading utilities for nanonispy2.

This module provides classes and functions for reading binary data from
Nanonis files with proper error handling and validation.
"""

from typing import Optional, Tuple

import numpy as np

from ..core.exceptions import CorruptedDataError, DimensionMismatchError
from ..core.validators import validate_file_path
from .formats import get_dtype, DEFAULT_FORMAT


class BinaryReader:
    """
    Binary data reader for Nanonis files.

    Provides methods for reading binary data from files with specified
    formats and proper error handling.

    Parameters
    ----------
    file_path : str
        Path to the binary file.
    byte_offset : int
        Position in file where data begins (after header).
    data_format : str, optional
        Name of the data format. If None, uses default format.

    Attributes
    ----------
    file_path : str
        Absolute path to the file.
    byte_offset : int
        Byte position where data begins.
    dtype : str
        NumPy dtype string for reading data.
    """

    def __init__(
        self,
        file_path: str,
        byte_offset: int,
        data_format: Optional[str] = None
    ):
        """
        Initialize binary reader.

        Parameters
        ----------
        file_path : str
            Path to the binary file.
        byte_offset : int
            Position in file where data begins.
        data_format : str, optional
            Name of the data format.
        """
        self.file_path = validate_file_path(file_path)
        self.byte_offset = byte_offset
        self.dtype = get_dtype(data_format)

    def read_array(
        self,
        expected_size: Optional[int] = None,
        validate: bool = True
    ) -> np.ndarray:
        """
        Read binary data as a 1D numpy array.

        Parameters
        ----------
        expected_size : int, optional
            Expected number of elements. If provided and validation is enabled,
            raises error if actual size doesn't match.
        validate : bool, default True
            Whether to validate the read data.

        Returns
        -------
        numpy.ndarray
            1D array of read data.

        Raises
        ------
        CorruptedDataError
            If file cannot be read or data appears corrupted.
        DimensionMismatchError
            If validation is enabled and size doesn't match expected_size.
        """
        try:
            with open(self.file_path, 'rb') as f:
                f.seek(self.byte_offset)
                data = np.fromfile(f, dtype=self.dtype)
        except Exception as e:
            raise CorruptedDataError(
                f"Failed to read binary data from {self.file_path}: {e}"
            )

        if validate:
            if data.size == 0:
                raise CorruptedDataError(
                    f"No data found after byte offset {self.byte_offset}"
                )

            if expected_size is not None and data.size != expected_size:
                raise DimensionMismatchError(
                    f"Expected {expected_size} elements, found {data.size}"
                )

        return data

    def read_shaped_array(
        self,
        shape: Tuple[int, ...],
        validate: bool = True
    ) -> np.ndarray:
        """
        Read and reshape binary data to specified dimensions.

        Parameters
        ----------
        shape : tuple of int
            Target shape for the data.
        validate : bool, default True
            Whether to validate reshape operation.

        Returns
        -------
        numpy.ndarray
            Array reshaped to specified dimensions.

        Raises
        ------
        DimensionMismatchError
            If data cannot be reshaped to target shape.
        """
        expected_size = np.prod(shape)
        data = self.read_array(expected_size=expected_size, validate=validate)

        try:
            return data.reshape(shape)
        except ValueError as e:
            raise DimensionMismatchError(
                f"Cannot reshape array of size {data.size} to {shape}: {e}"
            )

    def read_partial(
        self,
        start_idx: int,
        length: int
    ) -> np.ndarray:
        """
        Read a portion of the binary data.

        Parameters
        ----------
        start_idx : int
            Starting index (in elements, not bytes).
        length : int
            Number of elements to read.

        Returns
        -------
        numpy.ndarray
            1D array containing the requested data slice.

        Raises
        ------
        CorruptedDataError
            If file cannot be read.
        """
        dtype_obj = np.dtype(self.dtype)
        byte_start = self.byte_offset + start_idx * dtype_obj.itemsize

        try:
            with open(self.file_path, 'rb') as f:
                f.seek(byte_start)
                data = np.fromfile(f, dtype=self.dtype, count=length)
        except Exception as e:
            raise CorruptedDataError(
                f"Failed to read partial data from {self.file_path}: {e}"
            )

        if data.size != length:
            raise CorruptedDataError(
                f"Expected to read {length} elements, got {data.size}"
            )

        return data

    def get_data_size(self) -> int:
        """
        Calculate number of data elements in file.

        Returns
        -------
        int
            Number of data elements (not bytes) after byte_offset.

        Raises
        ------
        CorruptedDataError
            If file size cannot be determined.
        """
        try:
            import os
            file_size = os.path.getsize(self.file_path)
            data_bytes = file_size - self.byte_offset
            dtype_obj = np.dtype(self.dtype)
            return data_bytes // dtype_obj.itemsize
        except Exception as e:
            raise CorruptedDataError(
                f"Failed to determine data size: {e}"
            )


def read_binary_file(
    file_path: str,
    byte_offset: int,
    shape: Optional[Tuple[int, ...]] = None,
    data_format: Optional[str] = None
) -> np.ndarray:
    """
    Convenience function to read binary data from a file.

    Parameters
    ----------
    file_path : str
        Path to the binary file.
    byte_offset : int
        Position in file where data begins.
    shape : tuple of int, optional
        If provided, reshapes data to this shape.
    data_format : str, optional
        Name of the data format.

    Returns
    -------
    numpy.ndarray
        Array containing the binary data.
    """
    reader = BinaryReader(file_path, byte_offset, data_format)

    if shape is not None:
        return reader.read_shaped_array(shape)
    else:
        return reader.read_array()


def validate_binary_size(
    file_path: str,
    byte_offset: int,
    expected_size: int,
    data_format: Optional[str] = None
) -> bool:
    """
    Validate that binary file has expected data size.

    Parameters
    ----------
    file_path : str
        Path to the binary file.
    byte_offset : int
        Position in file where data begins.
    expected_size : int
        Expected number of elements.
    data_format : str, optional
        Name of the data format.

    Returns
    -------
    bool
        True if size matches expectation.

    Raises
    ------
    DimensionMismatchError
        If size doesn't match.
    """
    reader = BinaryReader(file_path, byte_offset, data_format)
    actual_size = reader.get_data_size()

    if actual_size != expected_size:
        raise DimensionMismatchError(
            f"File contains {actual_size} elements, expected {expected_size}"
        )

    return True

