"""
Writer for Nanonis point spectroscopy (.dat) files.

File layout (verified on Nanonis Generic 5 bias-spectroscopy files):

- CRLF line endings throughout, including after the last data row.
- Header lines ``key<TAB>value<TAB>``, the first being
  ``Experiment<TAB>bias spectroscopy<TAB>``, then one empty line.
- ``[DATA]``, then a tab-separated line of column names with units
  (e.g. ``Bias calc (V)``, ``Current (A) [filt]``), then tab-separated
  rows without a trailing tab.
- Numbers in engineering notation with 8 significant digits, e.g.
  ``9.9999998E-3``, ``-146.39633E-9``; missing values are ``NaN``.

Precision
---------
The Nanonis style (``precision=8``) keeps 8 significant digits, a
relative rounding error of at most 5e-8. That is below float32
resolution for most values but is **not** lossless: exact float32
round-trips need 9 digits and float64 needs up to 17. ``precision=None``
writes the shortest digit string that reads back as exactly the same
float64, at the cost of longer, non-Nanonis-looking numbers.

Not supported: backward sweeps (``[bwd]`` columns) and multi-sweep
columns are written only if you name the columns yourself; nanonispy2
does not generate their names, because no real file with them was
available to verify the naming.
"""

from collections.abc import Mapping
from typing import Any, Dict, List, Optional

import numpy as np

from .common import check_target, check_text_field
from .numfmt import format_eng, format_eng_exact

DAT_NEWLINE = '\r\n'
DATA_TAG = '[DATA]'


def _header_value(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return format_eng_exact(value)
    if isinstance(value, (list, tuple)):
        return ';'.join(_header_value(key, v) for v in value)
    return check_text_field('' if value is None else value,
                            f"Header value for '{key}'")


def render_dat_header(header: Mapping, experiment: Optional[str] = None) -> str:
    """
    Render a header dict as .dat header text, up to and including ``[DATA]``.

    ``Experiment`` is always written first. If *header* has no
    ``Experiment`` entry, *experiment* (default ``'bias spectroscopy'``)
    is used.

    Values: str as-is, bool → TRUE/FALSE, int as-is, float in Nanonis
    header style (``10E-3``; more digits if needed to be exact), list or
    tuple → ``;``-joined.
    """
    items = dict(header)
    exp = items.pop('Experiment', None)
    if exp is None:
        exp = 'bias spectroscopy' if experiment is None else experiment
    lines = [f"Experiment\t{_header_value('Experiment', exp)}\t"]
    for key, value in items.items():
        key = check_text_field(key, 'Header key')
        if not key or key == DATA_TAG:
            raise ValueError(f"Invalid header key {key!r}")
        lines.append(f"{key}\t{_header_value(key, value)}\t")
    lines += ['', DATA_TAG]
    return DAT_NEWLINE.join(lines) + DAT_NEWLINE


def _columns(signals: Mapping) -> List[np.ndarray]:
    if not isinstance(signals, Mapping) or len(signals) == 0:
        raise ValueError("signals must be a non-empty dict of column name -> 1-D array")
    errors = []
    arrays = []
    for name, values in signals.items():
        check_text_field(name, 'Column name')
        if not str(name).strip():
            errors.append("Column names must not be empty")
        arr = np.asarray(values)
        if arr.ndim != 1:
            errors.append(f"Column '{name}' must be 1-D, got shape {arr.shape}")
            continue
        if not np.issubdtype(arr.dtype, np.number) or \
                np.issubdtype(arr.dtype, np.complexfloating):
            errors.append(f"Column '{name}' has non-real dtype {arr.dtype}")
            continue
        arrays.append(arr.astype(np.float64))
    if not errors:
        lengths = {len(a) for a in arrays}
        if len(lengths) > 1:
            errors.append(
                "Columns have different lengths: "
                + ", ".join(f"'{n}': {len(a)}" for n, a in zip(signals, arrays))
            )
    if errors:
        raise ValueError("Invalid spectroscopy data.\n"
                         + "\n".join(f"  • {e}" for e in errors))
    return arrays


def write_dat_file(fname, header_bytes: bytes, signals: Mapping,
                   precision: Optional[int] = 8, overwrite: bool = False) -> None:
    """
    Write a .dat file from complete header bytes (ending in ``[DATA]``)
    and column data. Shared back end of :meth:`Spec.write` and
    :func:`write_dat`.
    """
    check_target(fname, '.dat', overwrite)
    if not header_bytes.rstrip(b'\r\n').endswith(DATA_TAG.encode()):
        raise ValueError("Header must end with the '[DATA]' line.")
    if precision is not None and (isinstance(precision, bool) or int(precision) < 1):
        raise ValueError(f"precision must be a positive int or None, got {precision!r}")
    if not header_bytes.endswith(b'\n'):
        header_bytes += DAT_NEWLINE.encode()
    arrays = _columns(signals)

    lines = ['\t'.join(str(k) for k in signals)]
    for row in zip(*arrays):
        lines.append('\t'.join(format_eng(v, precision) for v in row))
    body = DAT_NEWLINE.join(lines) + DAT_NEWLINE

    with open(fname, 'wb') as fh:
        fh.write(header_bytes)
        fh.write(body.encode('utf-8'))


def write_dat(
    fname,
    signals: Mapping,
    header: Optional[Dict[str, Any]] = None,
    *,
    experiment: str = 'bias spectroscopy',
    precision: Optional[int] = 8,
    overwrite: bool = False,
) -> None:
    """
    Create a Nanonis point spectroscopy (.dat) file from scratch.

    Parameters
    ----------
    fname : str or path-like
        Output path, must end with ``.dat``.
    signals : dict
        ``{column name: 1-D array}`` in column order. Names should carry
        their unit as Nanonis does, e.g. ``'Bias calc (V)'``,
        ``'Current (A)'``, ``'Current (A) [filt]'``. All columns must
        have the same length. NaN is written as ``NaN``.
    header : dict, optional
        Header ``{key: value}`` pairs in order, e.g.
        ``{'Saved Date': '02.12.2025 22:07:38', 'X (m)': 139.66e-9,
        'Bias Spectroscopy>Sweep Start (V)': 10e-3}``. Values may be
        str, bool (TRUE/FALSE), int, float (Nanonis header style) or a
        list (``;``-joined). No entries are added except ``Experiment``.
    experiment : str, optional
        Value of the first header line ``Experiment`` if *header* has
        none. Default ``'bias spectroscopy'``.
    precision : int or None, optional
        Significant digits of data values. Default 8 (Nanonis style,
        relative error ≤ 5e-8, not lossless); ``None`` writes the
        shortest exact float64 representation.
    overwrite : bool, optional
        Replace an existing file. Default False.

    Examples
    --------
    >>> import numpy as np
    >>> from nanonispy2 import write_dat
    >>> v = np.linspace(-0.1, 0.1, 201)
    >>> write_dat('demo.dat', {'Bias calc (V)': v, 'Current (A)': 1e-9 * v},
    ...           {'Saved Date': '01.01.2026 12:00:00', 'X (m)': 0.0})
    """
    check_target(fname, '.dat', overwrite)
    text = render_dat_header(header or {}, experiment=experiment)
    write_dat_file(fname, text.encode('utf-8'), signals,
                   precision=precision, overwrite=overwrite)


__all__ = ['write_dat', 'write_dat_file', 'render_dat_header']
