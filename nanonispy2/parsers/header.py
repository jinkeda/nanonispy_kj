"""
Header parsing utilities for Nanonis files.

This module provides functions to parse headers from different Nanonis
file types into structured dictionaries.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.exceptions import (
    MissingHeaderEntryError,
    InvalidHeaderValueError,
)


def split_header_entry(entry: str) -> Tuple[str, Any]:
    """
    Split a header entry by '=' delimiter and parse values.

    Parameters
    ----------
    entry : str
        Header entry string to split.

    Returns
    -------
    tuple
        (key, value) where value is either a string or list of strings.
    """
    key_str, val_str = entry.split("=", 1)

    if ';' in val_str:
        return key_str, val_str.strip('"').split(';')
    else:
        return key_str, val_str.strip('"')


def parse_grid_header(
    header_raw: str,
    header_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse raw header string from a grid (.3ds) file.

    Parameters
    ----------
    header_raw : str
        Raw header string from file.
    header_override : dict, optional
        Dictionary of key:value pairs to override header values.

    Returns
    -------
    dict
        Parsed header with appropriate type conversions.

    Raises
    ------
    MissingHeaderEntryError
        If required header entries are missing.
    InvalidHeaderValueError
        If header values cannot be parsed correctly.
    """
    # Split and clean header entries
    header_entries = header_raw.split('\r\n')[:-2]

    # Parse into raw dictionary
    raw_dict = {}
    for entry in header_entries:
        if '=' in entry:
            key, val = split_header_entry(entry)
            raw_dict[key] = val

    # Apply overrides
    if header_override is not None:
        raw_dict.update(header_override)

    # Build structured header dictionary
    header_dict = {}

    try:
        # Grid dimensions in pixels
        header_dict['dim_px'] = [
            int(val) for val in raw_dict['Grid dim'].split(' x ')
        ]
        raw_dict.pop('Grid dim')

        # Grid frame center position, size, angle
        grid_settings = raw_dict['Grid settings']
        header_dict['pos_xy'] = [float(val) for val in grid_settings[:2]]
        header_dict['size_xy'] = [float(val) for val in grid_settings[2:4]]
        header_dict['angle'] = float(grid_settings[4])
        raw_dict.pop('Grid settings')

        # Sweep signal
        header_dict['sweep_signal'] = raw_dict['Sweep Signal']
        raw_dict.pop('Sweep Signal')

        # Fixed parameters (a single entry has no ';' and parses as str)
        fixed = raw_dict['Fixed parameters']
        header_dict['fixed_parameters'] = [fixed] if isinstance(fixed, str) else fixed
        raw_dict.pop('Fixed parameters')

        # Experimental parameters
        experimental = raw_dict['Experiment parameters']
        header_dict['experimental_parameters'] = (
            [experimental] if isinstance(experimental, str) else experimental
        )
        raw_dict.pop('Experiment parameters')

        # Number of parameters (each 4 bytes)
        header_dict['num_parameters'] = int(raw_dict['# Parameters (4 byte)'])
        raw_dict.pop('# Parameters (4 byte)')

        # Experiment size in bytes
        header_dict['experiment_size'] = int(raw_dict['Experiment size (bytes)'])
        raw_dict.pop('Experiment size (bytes)')

        # Number of points of sweep signal
        header_dict['num_sweep_signal'] = int(raw_dict['Points'])
        raw_dict.pop('Points')

        # Channel names
        channels = raw_dict['Channels']
        if isinstance(channels, str):
            # Convert single channel to list
            header_dict['channels'] = [channels]
        else:
            header_dict['channels'] = channels
        header_dict['num_channels'] = len(header_dict['channels'])
        raw_dict.pop('Channels')

        # Measure delay
        header_dict['measure_delay'] = float(raw_dict['Delay before measuring (s)'])
        raw_dict.pop('Delay before measuring (s)')

        # Metadata
        header_dict['experiment_name'] = raw_dict.get('Experiment', '')
        header_dict['start_time'] = raw_dict.get('Start time', '')
        header_dict['end_time'] = raw_dict.get('End time', '')
        header_dict['user'] = raw_dict.get('User', '')
        header_dict['comment'] = raw_dict.get('Comment', '')

        for key in ['Experiment', 'Start time', 'End time', 'User', 'Comment']:
            raw_dict.pop(key, None)

    except KeyError as e:
        raise MissingHeaderEntryError(
            f"Missing required header entry: {e.args[0]}. "
            "You can use header_override to provide missing values."
        )
    except (ValueError, IndexError) as e:
        raise InvalidHeaderValueError(
            f"Cannot parse header value: {e}. "
            "You can use header_override to correct invalid values."
        )

    # Add any remaining entries to header
    header_dict.update(raw_dict)

    return header_dict


def parse_scan_header(header_raw: str) -> Dict[str, Any]:
    """
    Parse raw header string from a scan (.sxm) file.

    Parameters
    ----------
    header_raw : str
        Raw header string from file.

    Returns
    -------
    dict
        Parsed header with appropriate type conversions.
        ``scan_pixels`` is always ``[nx, ny]`` (samples per line, lines):
        files with ``NANONIS_VERSION`` < 2 store it as ``ny nx`` and are
        swapped here.
    """
    header_entries = header_raw.split('\n')
    # Everything from the ':SCANIT_END:' line on is not header
    for idx, entry in enumerate(header_entries):
        if entry.strip() == ':SCANIT_END:':
            header_entries = header_entries[:idx]
            break
    header_dict = {}

    # Define entry types for processing
    entries_to_split = [
        'scan_offset', 'scan_pixels', 'scan_range', 'scan_time'
    ]
    entries_to_float = [
        'scan_offset', 'scan_range', 'scan_time', 'bias', 'acq_time'
    ]
    entries_to_int = ['scan_pixels']
    entries_as_tables = [
        ':DATA_INFO:', ':Z-CONTROLLER:', ':Multipass-Config:'
    ]
    entries_multiline = [':COMMENT:']

    # Parse entries
    i = 0
    while i < len(header_entries):
        entry = header_entries[i]

        # Handle table entries
        if entry in entries_as_tables:
            # Find extent of table
            count = 1
            for j in range(i + 1, len(header_entries)):
                if header_entries[j].startswith(':'):
                    break
                if header_entries[j].startswith('\t'):
                    count += 1
            header_dict[entry.strip(':').lower()] = parse_scan_header_table(
                header_entries[i + 1:i + count]
            )
            i += 1
            continue

        # Handle multiline entries
        if entry in entries_multiline:
            multilines = []
            for j in range(i + 1, len(header_entries)):
                if header_entries[j].startswith(':'):
                    break
                multilines.append(header_entries[j])
            header_dict[entry.strip(':').lower()] = '\n'.join(multilines)
            i += 1
            continue

        # Handle simple key:value entries
        if entry.startswith(':'):
            if i + 1 < len(header_entries):
                header_dict[entry.strip(':').lower()] = header_entries[i + 1].strip()
            i += 1

        i += 1

    # Post-process: split values
    for key in entries_to_split:
        if key in header_dict:
            header_dict[key] = header_dict[key].split()

    # Post-process: convert to floats
    for key in entries_to_float:
        if key in header_dict:
            if isinstance(header_dict[key], list):
                header_dict[key] = np.asarray(header_dict[key], dtype=np.float64)
            else:
                header_dict[key] = np.float64(header_dict[key])

    # Post-process: convert to ints
    for key in entries_to_int:
        if key in header_dict:
            header_dict[key] = np.asarray(header_dict[key], dtype=np.int32)

    # NANONIS_VERSION < 2 stores SCAN_PIXELS as 'ny nx'
    if 'scan_pixels' in header_dict and _scan_version(header_dict) < 2:
        header_dict['scan_pixels'] = header_dict['scan_pixels'][::-1].copy()

    return header_dict


SCAN_DIRECTIONS = {
    'both': ('forward', 'backward'),
    'forward': ('forward',),
    'backward': ('backward',),
}


def _scan_version(header_dict: Dict[str, Any]) -> int:
    """Return NANONIS_VERSION as int (2 if absent or unparsable)."""
    try:
        return int(str(header_dict.get('nanonis_version', '2')).strip())
    except ValueError:
        return 2


def scan_channel_layout(header: Dict[str, Any]) -> List[Tuple[str, Tuple[str, ...]]]:
    """
    Frame layout of the binary data block of a parsed .sxm header.

    Channels are stored in DATA_INFO order. A ``both`` channel stores
    its forward frame then its backward frame; a ``forward`` or
    ``backward`` channel stores one frame.

    Parameters
    ----------
    header : dict
        Header as returned by :func:`parse_scan_header`.

    Returns
    -------
    list of (str, tuple of str)
        ``(channel name, recorded directions)`` in file order.

    Raises
    ------
    InvalidHeaderValueError
        If DATA_INFO is missing or a Direction value is not one of
        'both', 'forward', 'backward'.
    """
    data_info = header.get('data_info')
    if not data_info or 'Name' not in data_info:
        raise InvalidHeaderValueError("Scan header has no usable DATA_INFO table.")
    names = list(data_info['Name'])
    # Files without a Direction column: assume both directions
    directions = list(data_info.get('Direction', ('both',) * len(names)))

    layout = []
    for name, direction in zip(names, directions):
        key = direction.strip().lower()
        if key not in SCAN_DIRECTIONS:
            raise InvalidHeaderValueError(
                f"Channel '{name}' has unknown direction '{direction}'. "
                f"Expected one of {sorted(SCAN_DIRECTIONS)}."
            )
        layout.append((name, SCAN_DIRECTIONS[key]))
    return layout


def parse_scan_header_table(table_list: List[str]) -> Dict[str, Tuple]:
    """
    Parse tab-separated table from scan file header.

    Parameters
    ----------
    table_list : list of str
        List of table row strings.

    Returns
    -------
    dict
        Dictionary mapping column names to tuples of values.
    """
    table_processed = []
    for row in table_list:
        # Strip leading tab, split by tab
        table_processed.append(row.strip('\t').split('\t'))

    # First row contains column names
    keys = table_processed[0]
    values = table_processed[1:]

    # Transpose values
    zip_vals = zip(*values)

    return dict(zip(keys, zip_vals))


def parse_spec_header(header_raw: str) -> Dict[str, str]:
    """
    Parse raw header string from a spec (.dat) file.

    Parameters
    ----------
    header_raw : str
        Raw header string from file.

    Returns
    -------
    dict
        Parsed header dictionary.
    """
    header_entries = header_raw.split('\r\n')[:-3]
    header_dict = {}

    for entry in header_entries:
        # Normalize tab delimiters
        if entry.endswith('\t'):
            entry = entry[:-1]
        if '\t' not in entry:
            entry += '\t'

        # Split and store
        if '\t' in entry:
            key, val = entry.split('\t', 1)
            header_dict[key] = val

    return header_dict

