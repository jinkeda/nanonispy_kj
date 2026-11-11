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
from ..writers.sxm import write_scan_file
from .header import parse_scan_header, scan_channel_layout


class Scan(NanonisFile):
    """
    Nanonis scan file class.

    Contains data loading methods specific to Nanonis sxm files. The
    header is terminated by a 'SCANIT_END' tag followed by the \\1A\\04
    code. The NanonisFile header parse method doesn't account for this
    so the Scan __init__ method just adds 4 bytes to the byte_offset
    attribute so as to not include this as a datapoint.

    Data is structured a little differently from grid files, obviously.
    Channels are stored in DATA_INFO order, one (ny, nx) frame per
    recorded direction: a 'both' channel stores its forward frame then
    its backward frame, a 'forward' or 'backward' channel one frame.
    Arrays are returned in raw file order without flips (line 0 is the
    first line acquired; backward lines run right to left).

    Incomplete (aborted) scans are read as long as the file has its full
    size; unmeasured lines are NaN.

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
        another dict whose keys are the recorded directions ('forward'
        and/or 'backward') and whose values are the (ny, nx) arrays.

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
        nx, ny = (int(v) for v in self.header['scan_pixels'])

        # Frames per channel from the DATA_INFO 'Direction' column:
        # 'both' = forward then backward frame, 'forward'/'backward' = one
        layout = scan_channel_layout(self.header)
        nframes = sum(len(dirs) for _, dirs in layout)

        data_dict = dict()

        # open and seek to start of data
        with open(self.fname, 'rb') as f:
            f.seek(self.byte_offset)
            scandata = np.fromfile(f, dtype=self.data_format)

        # reshape
        expected_size = nframes * ny * nx
        if scandata.size != expected_size:
            raise CorruptedDataError(
                f"{self.basename}: expected {expected_size} data points "
                f"({len(layout)} channels, {nframes} frames × {ny} × {nx} pixels) "
                f"but found {scandata.size}. File may be truncated or corrupted."
            )
        frames = scandata.reshape(nframes, ny, nx)

        # extract data for each channel, exposing only recorded directions
        k = 0
        for chann, directions in layout:
            chann_dict = dict()
            for direction in directions:
                chann_dict[direction] = frames[k]
                k += 1
            data_dict[chann] = chann_dict

        return data_dict

    def write(self, fname, signals=None, header_raw=None, overwrite=False,
              encoding='utf-8'):
        """
        Write a Nanonis scan (sxm) file to disk.

        With no arguments this reproduces the loaded file byte for byte.
        Arrays are written in exactly the raw order :class:`Scan`
        returns them, with no flips: line 0 is the first line acquired
        (top of the frame for ``SCAN_DIR = down``, bottom for ``up``)
        and backward lines are stored in acquisition order, i.e. right
        to left. Data are always written as big-endian float32
        (``FLOAT MSBFIRST``); NaN is written as-is.

        Parameters
        ----------
        fname : str or path-like
            Output file path. Must end with ``.sxm``.
        signals : dict, optional
            ``{channel: {direction: (ny, nx) array}}``. Defaults to
            ``self.signals``. Each channel must have exactly the
            directions its DATA_INFO row records.
        header_raw : str or bytes, optional
            Header text to write, starting with ``:NANONIS_VERSION:``.
            Anything from ``:SCANIT_END:`` on is replaced by the standard
            terminator. Defaults to the original header bytes.
        overwrite : bool, optional
            If False (default), raise ``FileExistsError`` when *fname*
            already exists.
        encoding : str, optional
            Encoding used if *header_raw* is a str. Defaults to UTF-8.

        Raises
        ------
        UnhandledFileError
            If *fname* does not end with ``.sxm``.
        FileExistsError
            If *fname* exists and *overwrite* is False.
        ValueError
            If the header does not match the signal arrays (pixels,
            channel names, directions), or declares little-endian data.
        """
        if header_raw is None:
            header = self.header_bytes
        elif isinstance(header_raw, bytes):
            header = header_raw
        else:
            header = header_raw.encode(encoding)
        signals_to_write = self.signals if signals is None else signals
        write_scan_file(fname, header, signals_to_write, overwrite=overwrite)


__all__ = ['Scan']
