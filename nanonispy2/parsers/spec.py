"""
Spec file parser for Nanonis .dat files.

Implements the Spec class for reading and writing Nanonis point
spectroscopy files, using the modular core/io/parsers infrastructure.
"""

import numpy as np

from ..core.base import NanonisFile
from ..writers.dat import render_dat_header, write_dat_file
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

    def write(self, fname, signals=None, header=None, overwrite=False,
              precision=8):
        """
        Write a Nanonis point spectroscopy (dat) file to disk.

        With no arguments this reproduces the loaded file byte for byte
        (Nanonis files store 8 significant digits, which ``precision=8``
        reproduces exactly).

        Parameters
        ----------
        fname : str or path-like
            Output file path. Must end with ``.dat``.
        signals : dict, optional
            ``{column name: 1-D array}`` in column order. Defaults to
            ``self.signals``.
        header : dict, optional
            Header key/value pairs. Defaults to ``self.header``. If that
            equals the header parsed from the file, the original header
            bytes are written unchanged; otherwise it is re-rendered as
            ``key<TAB>value<TAB>`` lines (see
            :func:`nanonispy2.writers.dat.render_dat_header`).
        overwrite : bool, optional
            If False (default), raise ``FileExistsError`` when *fname*
            already exists.
        precision : int or None, optional
            Significant digits of data values. 8 (default) is the Nanonis
            style: relative error up to 5e-8, so arbitrary float64 data
            are not reproduced exactly. ``None`` writes the shortest
            representation that reads back as the identical float64.

        Raises
        ------
        UnhandledFileError
            If *fname* does not end with ``.dat``.
        FileExistsError
            If *fname* exists and *overwrite* is False.
        ValueError
            If columns are not 1-D, have different lengths, or names or
            header entries contain tabs or line breaks.
        """
        header_dict = self.header if header is None else header
        if header_dict == parse_spec_header(self.header_raw):
            header_bytes = self.header_bytes
        else:
            header_bytes = render_dat_header(header_dict).encode('utf-8')
        signals_to_write = self.signals if signals is None else signals
        write_dat_file(fname, header_bytes, signals_to_write,
                       precision=precision, overwrite=overwrite)


__all__ = ['Spec']
