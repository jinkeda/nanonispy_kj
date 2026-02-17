"""
Base classes for nanonispy2 file handling.

This module provides the base NanonisFile class that handles common operations
for all Nanonis file types, including header detection and reading.
"""

import os
import warnings
from typing import Optional

from .exceptions import UnhandledFileError, FileHeaderNotFoundError
from .validators import validate_file_path


# File type end tags mapping
NANONIS_END_TAGS = {
    'grid': ':HEADER_END:',
    'scan': 'SCANIT_END',
    'spec': '[DATA]'
}


class NanonisFile:
    """
    Base class for Nanonis data files (grid, scan, point spectroscopy).

    Handles methods and parsing tasks common to all Nanonis files, including
    file type detection, header location, and raw header reading.

    Parameters
    ----------
    fname : str
        Path to Nanonis file.

    Attributes
    ----------
    datadir : str
        Directory path for Nanonis file.
    basename : str
        Filename without path.
    fname : str
        Full absolute path of Nanonis file.
    filetype : str
        File type corresponding to filename extension ('grid', 'scan', or 'spec').
    byte_offset : int
        Size of header in bytes (position where data begins).
    header_raw : str
        Unprocessed header information as a string.

    Raises
    ------
    UnhandledFileError
        If the file extension is not supported.
    FileHeaderNotFoundError
        If the header end tag cannot be found in the file.
    """

    # Supported file extensions and their corresponding types
    SUPPORTED_EXTENSIONS = {
        '.3ds': 'grid',
        '.sxm': 'scan',
        '.dat': 'spec'
    }

    def __init__(self, fname: str):
        """
        Initialize NanonisFile with file path and determine file type.

        Parameters
        ----------
        fname : str
            Path to Nanonis file.
        """
        # Validate and store file path
        self.fname = validate_file_path(fname)
        self.datadir, self.basename = os.path.split(self.fname)

        # Determine file type from extension
        self.filetype = self._determine_filetype()

        # Find where data begins (after header)
        self.byte_offset = self._find_byte_offset()

        # Read raw header string
        self.header_raw = self._read_raw_header()

    def _determine_filetype(self) -> str:
        """
        Determine file type from extension.

        Returns
        -------
        str
            File type name ('grid', 'scan', or 'spec').

        Raises
        ------
        UnhandledFileError
            If file extension is not supported.
        """
        _, fname_ext = os.path.splitext(self.fname)

        if fname_ext not in self.SUPPORTED_EXTENSIONS:
            raise UnhandledFileError(
                f"{self.basename} has unsupported extension '{fname_ext}'. "
                f"Supported extensions: {', '.join(self.SUPPORTED_EXTENSIONS.keys())}"
            )

        return self.SUPPORTED_EXTENSIONS[fname_ext]

    def _find_byte_offset(self) -> int:
        """
        Find first byte after header end tag.

        The byte offset marks the position where binary/ASCII data begins,
        immediately after the header end tag and its terminating newline.

        Returns
        -------
        int
            Size of header in bytes.

        Raises
        ------
        FileHeaderNotFoundError
            If the expected end tag is not found in the file.
        """
        end_tag = NANONIS_END_TAGS[self.filetype]
        byte_offset = -1

        with open(self.fname, 'rb') as f:
            for line in f:
                try:
                    entry = line.strip().decode('utf-8')
                except UnicodeDecodeError:
                    warnings.warn(
                        f'{self.basename} contains non-UTF-8 characters, replacing them.',
                        UnicodeWarning
                    )
                    entry = line.strip().decode('utf-8', errors='replace')

                if end_tag in entry:
                    byte_offset = f.tell()
                    break

        if byte_offset == -1:
            raise FileHeaderNotFoundError(
                f"Could not find the '{end_tag}' end tag in {self.basename}"
            )

        return byte_offset

    def _read_raw_header(self) -> str:
        """
        Read raw header as a string.

        Everything before the end tag is considered part of the header.
        Parsing will be done later by subclass methods.

        Returns
        -------
        str
            Contents of file up to byte_offset as a decoded string.
        """
        with open(self.fname, 'rb') as f:
            header_bytes = f.read(self.byte_offset)
            return header_bytes.decode('utf-8', errors='replace')

    def __repr__(self) -> str:
        """
        Return string representation of NanonisFile object.

        Returns
        -------
        str
            String representation showing file type and name.
        """
        return f"{self.__class__.__name__}('{self.basename}', type='{self.filetype}')"

    def get_header_info(self) -> dict:
        """
        Get basic header information.

        Returns
        -------
        dict
            Dictionary containing basic file information.
        """
        return {
            'filename': self.basename,
            'filepath': self.fname,
            'filetype': self.filetype,
            'header_size_bytes': self.byte_offset,
        }

