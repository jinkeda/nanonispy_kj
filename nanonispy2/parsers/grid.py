"""
Grid file parser for Nanonis .3ds files.

Implements the Grid class for reading and writing Nanonis grid
spectroscopy files, using the modular core/io/parsers infrastructure.
"""

import re
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from ..core.base import NanonisFile
from ..core.exceptions import UnhandledFileError
from ..io.formats import get_dtype
from .header import parse_grid_header


# ---- Topo column resolver ----
_TOPO_BASE_ALIASES = {'z'}


def _resolve_topo_index(param_labels):
    """
    Find the Z-height column index by normalized label matching.

    Handles label variations across Nanonis versions:
    'Z (m)', 'Z [m]', 'Z (nm)', 'z', etc.

    Parameters
    ----------
    param_labels : list of str
        List of parameter labels from the 3ds header.

    Returns
    -------
    int
        Index of the Z-height column.
    """
    for i, label in enumerate(param_labels):
        normalized = label.strip().lower()
        # Strip unit brackets/parens: "Z (m)" → "z", "Z [nm]" → "z"
        base = re.sub(r'\s*[\(\[].*?[\)\]]', '', normalized).strip()
        if base in _TOPO_BASE_ALIASES:
            return i
    warnings.warn(
        f"Z column not found in {param_labels}, falling back to first parameter (index 0)",
        stacklevel=2
    )
    return 0


class Grid(NanonisFile):
    """
    Nanonis grid file class.

    Contains data loading method specific to Nanonis grid file. Nanonis
    3ds files contain a header terminated by '\\r\\n:HEADER_END:\\r\\n'
    line, after which big endian encoded binary data starts. A grid is
    always recorded in an 'up' direction, and data is recorded
    sequentially starting from the first pixel. The number of bytes
    corresponding to a single pixel will depend on the experiment
    parameters. In general the size of one pixel will be a sum of

        - # fixed parameters
        - # experimental parameters
        - # sweep signal points (typically bias).

    Hence if there are 2 fixed parameters, 8 experimental parameters,
    and a 512 point bias sweep, a pixel will account 4 x (522) = 2088
    bytes of data. The class intuits this from header info and extracts
    the data for you and cuts it up into each channel, though normally
    this should be just the current.

    Currently cannot accept grids that are incomplete.

    Parameters
    ----------
    fname : str
        Filename for grid file.
    header_override : dict, optional
        A dict of key:value to override any corresponding key:value should
        they be wrong or missing in your header. Keys in header_override must
        match keys in Grid.header_raw.
    data_format : str, optional
        Data format name (e.g. 'big endian float 32'). Uses default if None.

    Attributes
    ----------
    header : dict
        Parsed 3ds header. Relevant fields are converted to float,
        otherwise most are string values.
    signals : dict
        Dict keys correspond to channel name, with values being the
        corresponding data array.

    Raises
    ------
    UnhandledFileError
        If fname does not have a '.3ds' extension.
    """
    expected_filetype = 'grid'

    def __init__(
        self,
        fname: str,
        header_override: Optional[Dict[str, Any]] = None,
        data_format: Optional[str] = None
    ) -> None:
        super().__init__(fname)
        self.data_format = get_dtype(data_format)
        self.header = parse_grid_header(self.header_raw, header_override=header_override)
        self.signals = self._load_data()
        self.signals['sweep_signal'] = self._derive_sweep_signal()
        self.signals['topo'] = self._extract_topo()

    def _load_data(self):
        """
        Read binary data for Nanonis 3ds file.

        Returns
        -------
        dict
            Channel name keyed dict of 3d array.
        """
        # load grid params
        nx, ny = self.header['dim_px']
        num_sweep = self.header['num_sweep_signal']
        num_param = self.header['num_parameters']
        num_chan = self.header['num_channels']
        data_dict = dict()

        # open and seek to start of data
        with open(self.fname, 'rb') as f:
            f.seek(self.byte_offset)
            griddata = np.fromfile(f, dtype=self.data_format)

        # pixel size in elements
        exp_size_per_pix = num_param + num_sweep * num_chan
        expected_total = ny * nx * exp_size_per_pix

        if griddata.size == 0:
            from ..core.exceptions import CorruptedDataError
            raise CorruptedDataError(
                f"No binary data found after header in {self.basename}"
            )
        if griddata.size < expected_total:
            warnings.warn(
                f"{self.basename}: expected {expected_total} data points but "
                f"found {griddata.size}. File may be truncated; missing values "
                "will be zero-filled.",
                stacklevel=2
            )

        # resize from 1d to 3d (zero-fills if truncated)
        griddata.resize((ny, nx, exp_size_per_pix))

        # experimental parameters are first num_param of every pixel
        params = griddata[:, :, :num_param]
        data_dict['params'] = params

        # extract data for each channel
        for i, chann in enumerate(self.header['channels']):
            start_ind = num_param + i * num_sweep
            stop_ind = num_param + (i + 1) * num_sweep
            data_dict[chann] = griddata[:, :, start_ind:stop_ind]

        return data_dict

    def _derive_sweep_signal(self):
        """
        Compute sweep signal.

        Based on start and stop points of sweep signal in header, and
        number of sweep signal points.

        Returns
        -------
        numpy.ndarray
            1d sweep signal, should be sample bias in most cases.
        """
        # find sweep signal start and end from a given pixel value
        sweep_start, sweep_end = self.signals['params'][0, 0, :2]
        num_sweep_signal = self.header['num_sweep_signal']

        return np.linspace(sweep_start, sweep_end, num_sweep_signal, dtype=np.float32)

    def _extract_topo(self):
        """
        Extract topographic map based on z-controller height at each pixel.

        Uses label normalization to find the Z (m) column dynamically,
        falling back to index 4 with a warning if not found.

        Returns
        -------
        numpy.ndarray
            Copy of already extracted data to be more easily accessible
            in signals dict.
        """
        # Build combined parameter label list
        fixed = self.header.get('fixed_parameters', [])
        experimental = self.header.get('experimental_parameters', [])
        all_labels = fixed + experimental
        topo_idx = _resolve_topo_index(all_labels)
        return self.signals['params'][:, :, topo_idx]

    def write(self, fname, signals=None, header_raw=None, data_format=None,
              overwrite=False, encoding='utf-8'):
        """
        Write a Nanonis grid (3ds) file to disk.

        Parameters
        ----------
        fname : str or path-like
            Output file path. Must end with ``.3ds``.
        signals : dict, optional
            Mapping of data arrays to write. Defaults to ``self.signals``.
        header_raw : str or bytes, optional
            Header string to write. Defaults to the original header.
        data_format : str or numpy.dtype, optional
            Desired NumPy dtype for serialization.
        overwrite : bool, optional
            If False (default), raise ``FileExistsError`` when *fname*
            already exists.
        encoding : str, optional
            Text encoding used when writing header bytes. Defaults to UTF-8.
        """
        if not str(fname).endswith('.3ds'):
            raise UnhandledFileError(f"{fname} must have .3ds extension")
        if not overwrite and Path(fname).exists():
            raise FileExistsError(
                f"{fname} already exists. Set overwrite=True to replace it."
            )

        header_text = header_raw if header_raw is not None else self.header_raw
        if header_text is None:
            raise ValueError('No header information available to write.')
        if isinstance(header_text, bytes):
            header_bytes = header_text
        else:
            header_bytes = header_text.encode(encoding)

        if b':HEADER_END:' not in header_bytes:
            raise ValueError(
                "Header must contain ':HEADER_END:' terminator for 3ds files."
            )
        if not header_bytes.endswith(b'\r\n'):
            header_bytes += b'\r\n'

        dtype = self._resolve_grid_dtype(data_format)
        signals_to_write = self.signals if signals is None else signals

        # Validate header text matches actual data
        self._validate_header_data_consistency(header_bytes, signals_to_write)

        griddata = self._stack_signals_for_write(signals_to_write, dtype)

        with open(fname, 'wb') as fh:
            fh.write(header_bytes)
            griddata.tofile(fh)

    def _resolve_grid_dtype(self, data_format):
        """Return NumPy dtype for grid serialization."""
        if data_format is None:
            return np.dtype(self.data_format)
        elif isinstance(data_format, str):
            try:
                return np.dtype(get_dtype(data_format))
            except KeyError:
                return np.dtype(data_format)
        return np.dtype(data_format)

    def _stack_signals_for_write(self, signals, dtype):
        """Validate and stack signal arrays into binary payload."""
        nx, ny = self.header['dim_px']
        nx = int(nx)
        ny = int(ny)
        num_param = int(self.header['num_parameters'])
        num_sweep = int(self.header['num_sweep_signal'])
        channels = list(self.header['channels'])

        if 'params' not in signals:
            raise KeyError("signals dictionary must include a 'params' entry.")
        params = np.asarray(signals['params'])
        expected_shape = (ny, nx, num_param)
        if params.shape != expected_shape:
            raise ValueError(
                f"'params' array has shape {params.shape}, expected {expected_shape}."
            )

        exp_size_per_pix = num_param + num_sweep * len(channels)
        griddata = np.empty((ny, nx, exp_size_per_pix), dtype=dtype)
        griddata[:, :, :num_param] = params.astype(dtype, copy=False)

        for idx, channel in enumerate(channels):
            if channel not in signals:
                raise KeyError(f"signals missing required channel '{channel}'.")
            channel_data = np.asarray(signals[channel])
            channel_shape = (ny, nx, num_sweep)
            if channel_data.shape != channel_shape:
                raise ValueError(
                    f"Channel '{channel}' has shape {channel_data.shape}, "
                    f"expected {channel_shape}."
                )
            start = num_param + idx * num_sweep
            stop = start + num_sweep
            griddata[:, :, start:stop] = channel_data.astype(dtype, copy=False)

        return griddata

    def _validate_header_data_consistency(
        self,
        header_bytes: bytes,
        signals: dict
    ) -> None:
        """
        Check that the header text parameters match the actual signal data.

        Re-parses the header text and compares grid dimensions, parameter
        counts, sweep length, channel count, and channel names against
        the signal arrays. Raises ValueError on any mismatch.
        """
        from .header import parse_grid_header

        # Re-parse the header that will be written
        header_text = header_bytes.decode('utf-8', errors='replace')
        try:
            written_header = parse_grid_header(header_text)
        except Exception:
            # If header can't be parsed, skip validation
            # (user may be writing a custom header)
            return

        errors = []

        # --- Grid dimensions ---
        hdr_nx, hdr_ny = written_header['dim_px']
        if 'params' in signals:
            data_ny, data_nx = signals['params'].shape[:2]
            if (int(hdr_nx), int(hdr_ny)) != (data_nx, data_ny):
                errors.append(
                    f"Header dim_px ({hdr_nx}×{hdr_ny}) != "
                    f"data shape ({data_nx}×{data_ny})"
                )

        # --- Number of parameters ---
        hdr_num_param = int(written_header['num_parameters'])
        if 'params' in signals and signals['params'].ndim == 3:
            data_num_param = signals['params'].shape[2]
            if hdr_num_param != data_num_param:
                errors.append(
                    f"Header num_parameters ({hdr_num_param}) != "
                    f"params array depth ({data_num_param})"
                )

        # --- Sweep length ---
        hdr_num_sweep = int(written_header['num_sweep_signal'])
        hdr_channels = list(written_header['channels'])
        for ch in hdr_channels:
            if ch in signals:
                data_sweep = signals[ch].shape[-1]
                if hdr_num_sweep != data_sweep:
                    errors.append(
                        f"Header num_sweep_signal ({hdr_num_sweep}) != "
                        f"channel '{ch}' sweep length ({data_sweep})"
                    )
                break  # check only the first matching channel

        # --- Channel count ---
        hdr_num_chan = int(written_header['num_channels'])
        data_channels = [k for k in signals if k not in
                         ('params', 'sweep_signal', 'topo')]
        if hdr_num_chan != len(data_channels):
            errors.append(
                f"Header num_channels ({hdr_num_chan}) != "
                f"data channels ({len(data_channels)}): {data_channels}"
            )

        # --- Channel names ---
        missing = [ch for ch in hdr_channels if ch not in signals]
        if missing:
            errors.append(
                f"Header lists channels not found in signals: {missing}"
            )

        if errors:
            raise ValueError(
                "Header/data mismatch — the header text does not match "
                "the signal arrays. Fix the header or signals before writing.\n"
                + "\n".join(f"  • {e}" for e in errors)
            )


__all__ = ['Grid']
