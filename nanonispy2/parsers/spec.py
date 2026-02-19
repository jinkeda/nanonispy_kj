"""
Spec file parser for Nanonis .dat files.

Implements the Spec class for reading Nanonis point spectroscopy files,
using the modular core/io/parsers infrastructure.
"""

import numpy as np

from ..core.base import NanonisFile
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

    expected_filetype = 'spec'

    def __init__(self, fname: str) -> None:
        super().__init__(fname)
        self.header = parse_spec_header(self.header_raw)
        self.signals = self._load_data()

    def _load_data(self):
        """
        Load ascii formatted .dat file.

        Uses byte_offset to skip directly to the data section,
        avoiding a second full file read.

        Returns
        -------
        dict
            Keys correspond to each channel recorded, including
            saved/filtered versions of other channels.
        """
        data_dict = dict()

        with open(self.fname, 'r', encoding='utf-8', errors='replace') as f:
            f.seek(self.byte_offset)
            column_names = f.readline().strip('\n').split('\t')

            # Read remaining lines as data
            lines = f.readlines()

        if not lines:
            return data_dict

        # Parse data from remaining lines
        data_rows = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            row = []
            for x in line.split('\t'):
                try:
                    row.append(float(x))
                except ValueError:
                    row.append(float('nan'))
            data_rows.append(row)

        specdata = np.array(data_rows)

        for i, name in enumerate(column_names):
            data_dict[name] = specdata[:, i]

        return data_dict


__all__ = ['Spec']
