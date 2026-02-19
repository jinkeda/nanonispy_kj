"""
Scan file parser for Nanonis .sxm files.

Implements the Scan class for reading Nanonis scan files, using the
modular core/io/parsers infrastructure.
"""

from typing import Optional

import numpy as np

from ..core.base import NanonisFile
from ..core.exceptions import CorruptedDataError
from ..io.formats import get_dtype
from .header import parse_scan_header


class Scan(NanonisFile):
    """
    Nanonis scan file class.

    Contains data loading methods specific to Nanonis sxm files. The
    header is terminated by a 'SCANIT_END' tag followed by the \\1A\\04
    code. The NanonisFile header parse method doesn't account for this
    so the Scan __init__ method just adds 4 bytes to the byte_offset
    attribute so as to not include this as a datapoint.

    Data is structured a little differently from grid files, obviously.
    For each pixel in the scan, each channel is recorded forwards and
    backwards one after the other.

    Currently cannot take scans that do not have both directions
    recorded for each channel, nor incomplete scans.

    Parameters
    ----------
    fname : str
        Filename for scan file.
    data_format : str, optional
        Data format name (e.g. 'big endian float 32'). Uses default if None.

    Attributes
    ----------
    header : dict
        Parsed sxm header. Some fields are converted to float,
        otherwise most are string values.
    signals : dict
        Dict keys correspond to channel name, values correspond to
        another dict whose keys are simply forward and backward arrays
        for the scan image.

    Raises
    ------
    UnhandledFileError
        If fname does not have a '.sxm' extension.
    """
    expected_filetype = 'scan'

    def __init__(self, fname: str, data_format: Optional[str] = None) -> None:
        super().__init__(fname)
        self.data_format = get_dtype(data_format)
        self.header = parse_scan_header(self.header_raw)

        # data begins with 4 byte code, add 4 bytes to offset instead
        self.byte_offset += 4

        # load data
        self.signals = self._load_data()

    def _load_data(self):
        """
        Read binary data for Nanonis sxm file.

        Returns
        -------
        dict
            Channel name keyed dict of each channel array.
        """
        channs = list(self.header['data_info']['Name'])
        nchanns = len(channs)
        nx, ny = self.header['scan_pixels']

        # Determine number of scan directions from header
        # The 'Direction' field in data_info contains per-channel values
        # like 'both' (= forward + backward) or 'forward'/'backward'
        data_info = self.header.get('data_info', {})
        if 'Direction' in data_info:
            directions = data_info['Direction']
            # If any channel records 'both', there are 2 directions
            ndir = 2 if any(d.strip().lower() == 'both' for d in directions) else 1
        else:
            ndir = 2  # default: forward + backward

        data_dict = dict()

        # open and seek to start of data
        with open(self.fname, 'rb') as f:
            f.seek(self.byte_offset)
            scandata = np.fromfile(f, dtype=self.data_format)

        # reshape
        expected_size = nchanns * ndir * ny * nx
        if scandata.size != expected_size:
            raise CorruptedDataError(
                f"{self.basename}: expected {expected_size} data points "
                f"({nchanns} channels × {ndir} directions × {ny} × {nx} pixels) "
                f"but found {scandata.size}. File may be truncated or corrupted."
            )
        scandata_shaped = scandata.reshape(nchanns, ndir, ny, nx)

        # extract data for each channel
        for i, chann in enumerate(channs):
            chann_dict = dict(forward=scandata_shaped[i, 0, :, :],
                              backward=scandata_shaped[i, 1, :, :])
            data_dict[chann] = chann_dict

        return data_dict


__all__ = ['Scan']
