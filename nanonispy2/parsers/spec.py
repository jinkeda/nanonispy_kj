"""
Spec file parser for Nanonis .dat files.

Implements the Spec class for reading Nanonis point spectroscopy files,
using the modular core/io/parsers infrastructure.
"""

import os

import numpy as np

from ..core.base import NanonisFile, NANONIS_END_TAGS
from ..core.exceptions import UnhandledFileError
from .header import parse_spec_header


class Spec(NanonisFile):
    """
    Nanonis point spectroscopy file class.

    These files are a little easier to handle since they are stored in
    ascii format.

    Parameters
    ----------
    fname : str
        Filename for spec file.

    Attributes
    ----------
    header : dict
        Parsed dat header.
    signals : dict
        Column name keyed dict of 1d arrays.

    Raises
    ------
    UnhandledFileError
        If fname does not have a '.dat' extension.
    """

    def __init__(self, fname):
        # Validate extension before base class tries to find headers
        _, ext = os.path.splitext(fname)
        if ext.lower() != '.dat':
            raise UnhandledFileError(
                f"{os.path.basename(fname)} is not a .dat spec file"
            )
        super().__init__(fname)
        self.header = parse_spec_header(self.header_raw)
        self.signals = self._load_data()

    def _load_data(self):
        """
        Load ascii formatted .dat file.

        Header ended by '[DATA]' tag.

        Returns
        -------
        dict
            Keys correspond to each channel recorded, including
            saved/filtered versions of other channels.
        """
        # done differently since data is ascii, not binary
        data_dict = dict()

        with open(self.fname, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(self.byte_offset)
            column_names = f.readline().strip('\n').split('\t')

        num_lines = self._num_header_lines()
        specdata = np.genfromtxt(self.fname, delimiter='\t', skip_header=num_lines)

        for i, name in enumerate(column_names):
            data_dict[name] = specdata[:, i]

        return data_dict

    def _num_header_lines(self):
        """Number of lines the header is composed of."""
        with open(self.fname, 'r') as f:
            data = f.readlines()
            for i, line in enumerate(data):
                if NANONIS_END_TAGS['spec'] in line:
                    return i + 2  # add 2 to skip the tag itself and column names
        return 0


__all__ = ['Spec']
