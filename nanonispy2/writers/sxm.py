"""
Writer for Nanonis scan (.sxm) files.

File layout (verified byte for byte on Nanonis Generic 5 files; the
orientation conventions follow Gwyddion's importer):

- An LF-terminated text header starting with ``:NANONIS_VERSION:``.
  Each tag is a line ``:TAG:`` followed by one or more value lines.
  Tables (``Z-CONTROLLER``, ``DATA_INFO``) have tab-indented rows;
  DATA_INFO is followed by a blank line.
- ``:SCANIT_END:`` + ``\\n\\n\\n``, then the two bytes ``0x1A 0x04``.
- Big-endian float32 data. Channels are stored in DATA_INFO order; a
  ``both`` channel stores its forward frame then its backward frame, a
  ``forward``/``backward`` channel stores one frame. Each frame is
  ny lines × nx samples, with (nx, ny) from SCAN_PIXELS.

Orientation
-----------
The writer is the exact inverse of :class:`~nanonispy2.Scan`: arrays
are written in the raw file order that ``Scan`` returns, with **no
flips**. In that raw order (following Gwyddion's importer):

- line (row) 0 is the first line acquired: the **top** of the frame for
  ``SCAN_DIR = down`` and the **bottom** for ``SCAN_DIR = up``;
- forward frames run left to right;
- backward lines are stored in acquisition order, i.e. **right to
  left**.

To produce an image that displays correctly you must therefore arrange
your arrays in that order yourself (e.g. flip backward frames left-right
and up-scans top-bottom relative to the displayed image).

Aborted scans store NaN for lines that were never measured; NaN is
written as-is.
"""

import datetime
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from ..core.exceptions import NanonisError
from ..parsers.header import (
    SCAN_DIRECTIONS,
    parse_scan_header,
    scan_channel_layout,
)
from ._sxm_default import DEFAULT_SXM_HEADER
from .common import check_target, check_text_field
from .numfmt import format_eng, format_eng_exact, format_fixed, format_sci

SXM_DTYPE = np.dtype('>f4')
END_TAG = ':SCANIT_END:'
# ':SCANIT_END:' line end + two blank lines, then the 0x1A 0x04 code
END_BYTES = b':SCANIT_END:\n\n\n\x1a\x04'
_ENCODING = 'utf-8'
_ERRORS = 'surrogateescape'   # keeps undecodable header bytes intact

SCANIT_TYPE_LINE = '              FLOAT            MSBFIRST'

# Fixed tags in the order Nanonis writes them; used to place a tag that
# is missing from a template.
_PRIMARY_ORDER = [
    'NANONIS_VERSION', 'SCANIT_TYPE', 'REC_DATE', 'REC_TIME', 'REC_TEMP',
    'ACQ_TIME', 'SCAN_PIXELS', 'SCAN_FILE', 'SCAN_TIME', 'SCAN_RANGE',
    'SCAN_OFFSET', 'SCAN_ANGLE', 'SCAN_DIR', 'BIAS', 'Z-CONTROLLER',
    'COMMENT',
]
# Tags controlled by write_sxm arguments; not settable via extra_header
_ARG_TAGS = {
    'NANONIS_VERSION', 'SCANIT_TYPE', 'REC_DATE', 'REC_TIME', 'ACQ_TIME',
    'SCAN_PIXELS', 'SCAN_RANGE', 'SCAN_OFFSET', 'SCAN_ANGLE', 'SCAN_DIR',
    'BIAS', 'Z-CONTROLLER', 'COMMENT', 'DATA_INFO',
}
_DATA_INFO_COLUMNS = ['Channel', 'Name', 'Unit', 'Direction', 'Calibration', 'Offset']

Block = List[Any]   # [tag, [value lines]]


# ---------------------------------------------------------------- header text

def _header_text(header: Union[str, bytes]) -> str:
    """Decode a header and cut it just before ':SCANIT_END:'."""
    if isinstance(header, bytes):
        header = header.decode(_ENCODING, errors=_ERRORS)
    if not header.startswith(':NANONIS_VERSION:'):
        raise ValueError("SXM header must start with ':NANONIS_VERSION:'.")
    match = re.search(r'^:SCANIT_END:', header, flags=re.MULTILINE)
    if match is not None:
        header = header[:match.start()]
    if not header.endswith('\n'):
        header += '\n'
    return header


def header_to_bytes(header: Union[str, bytes]) -> bytes:
    """
    Full on-disk header: text up to ``:SCANIT_END:`` plus terminator.

    Everything after the ``:SCANIT_END:`` tag in *header* (if present)
    is replaced by the canonical ``\\n\\n\\n\\x1a\\x04`` sequence.
    """
    return _header_text(header).encode(_ENCODING, errors=_ERRORS) + END_BYTES


def split_header_blocks(text: str) -> List[Block]:
    """
    Split header text (without ``:SCANIT_END:``) into ``[tag, lines]``.

    A tag line is a line of the form ``:TAG:``; every following line up
    to the next tag line belongs to that tag. ``render_header_blocks``
    is the exact inverse.
    """
    blocks: List[Block] = []
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
    for line in lines:
        if _is_tag_line(line):
            blocks.append([line[1:-1], []])
        elif blocks:
            blocks[-1][1].append(line)
        else:
            raise ValueError(f"Header text does not start with a tag: {line!r}")
    return blocks


def render_header_blocks(blocks: Sequence[Block]) -> str:
    """Inverse of :func:`split_header_blocks`."""
    out = []
    for tag, lines in blocks:
        out.append(f':{tag}:')
        out.extend(lines)
    return '\n'.join(out) + '\n'


def _is_tag_line(line: str) -> bool:
    return len(line) >= 2 and line.startswith(':') and line.endswith(':') \
        and '\t' not in line


def _find(blocks: List[Block], tag: str) -> Optional[Block]:
    for block in blocks:
        if block[0] == tag:
            return block
    return None


def _set(blocks: List[Block], tag: str, lines: List[str]) -> None:
    """Replace a tag's value lines, inserting the tag if missing."""
    block = _find(blocks, tag)
    if block is not None:
        block[1] = list(lines)
        return
    new = [tag, list(lines)]
    if tag in _PRIMARY_ORDER:
        later = _PRIMARY_ORDER[_PRIMARY_ORDER.index(tag) + 1:]
        for i, (other, _) in enumerate(blocks):
            if other in later:
                blocks.insert(i, new)
                return
    # otherwise: before DATA_INFO, which Nanonis always writes last
    for i, (other, _) in enumerate(blocks):
        if other == 'DATA_INFO':
            blocks.insert(i, new)
            return
    blocks.append(new)


def _set_if_present(blocks: List[Block], tag: str, lines: List[str]) -> None:
    block = _find(blocks, tag)
    if block is not None:
        block[1] = list(lines)


# ------------------------------------------------------------- binary data

def stack_scan_frames(header: Dict[str, Any], signals: Mapping) -> np.ndarray:
    """
    Validate *signals* against a parsed header and serialize the frames.

    Parameters
    ----------
    header : dict
        Parsed header (:func:`parse_scan_header`).
    signals : mapping
        ``{channel: {direction: (ny, nx) array}}`` with exactly the
        directions DATA_INFO records for each channel.

    Returns
    -------
    numpy.ndarray
        1-D big-endian float32 array in file order.

    Raises
    ------
    ValueError
        On any mismatch between header and signals (all problems are
        listed in one message).
    """
    try:
        layout = scan_channel_layout(header)
    except NanonisError as e:
        raise ValueError(str(e)) from None
    if 'scan_pixels' not in header:
        raise ValueError("Scan header has no SCAN_PIXELS entry.")
    nx, ny = (int(v) for v in header['scan_pixels'])

    errors = []
    names = [name for name, _ in layout]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        errors.append(f"DATA_INFO lists channel names more than once: {dupes}")
    extra = [k for k in signals if k not in names]
    if extra:
        errors.append(f"signals has channels not in the header DATA_INFO: {extra}")

    frames = []
    for name, directions in layout:
        if name not in signals:
            errors.append(f"signals missing channel '{name}'")
            continue
        chan = signals[name]
        if not isinstance(chan, Mapping):
            errors.append(
                f"signals['{name}'] must be a dict of direction -> array, "
                f"got {type(chan).__name__}"
            )
            continue
        if set(chan) != set(directions):
            errors.append(
                f"Channel '{name}' is recorded {list(directions)} in the "
                f"header but signals gives {sorted(chan)}"
            )
            continue
        for direction in directions:
            arr = np.asarray(chan[direction])
            if arr.shape != (ny, nx):
                errors.append(
                    f"signals['{name}']['{direction}'] has shape {arr.shape}, "
                    f"expected (ny, nx) = {(ny, nx)}"
                )
                continue
            if not np.issubdtype(arr.dtype, np.number) or \
                    np.issubdtype(arr.dtype, np.complexfloating):
                errors.append(
                    f"signals['{name}']['{direction}'] has non-real dtype {arr.dtype}"
                )
                continue
            frames.append(arr.astype(SXM_DTYPE).ravel())

    if errors:
        raise ValueError(
            "Header/data mismatch — the header does not match the signal "
            "arrays. Fix the header or signals before writing.\n"
            + "\n".join(f"  • {e}" for e in errors)
        )
    if not frames:
        return np.empty(0, dtype=SXM_DTYPE)
    # np.concatenate returns native byte order; force big-endian again
    return np.concatenate(frames).astype(SXM_DTYPE, copy=False)


def write_scan_file(fname, header: Union[str, bytes], signals: Mapping,
                    overwrite: bool = False) -> None:
    """
    Write an .sxm file from a complete header and signals.

    This is the shared back end of :meth:`Scan.write` and
    :func:`write_sxm`. See the module docstring for the layout and
    orientation conventions.

    Raises
    ------
    UnhandledFileError
        If *fname* does not end with ``.sxm``.
    FileExistsError
        If *fname* exists and *overwrite* is False.
    ValueError
        If the header is not a big-endian float header, or does not
        match *signals*.
    """
    check_target(fname, '.sxm', overwrite)
    header_bytes = header_to_bytes(header)
    text = header_bytes[:-2].decode(_ENCODING, errors='replace')
    parsed = parse_scan_header(text)

    scanit_type = str(parsed.get('scanit_type', 'FLOAT MSBFIRST')).split()
    if scanit_type != ['FLOAT', 'MSBFIRST']:
        raise ValueError(
            f"SCANIT_TYPE is '{' '.join(scanit_type)}'; only 'FLOAT MSBFIRST' "
            "(big-endian float32) can be written, because readers assume "
            "big-endian data."
        )

    data = stack_scan_frames(parsed, signals)
    with open(fname, 'wb') as fh:
        fh.write(header_bytes)
        data.tofile(fh)


# ------------------------------------------------------------ from scratch

ChannelSpec = Union[Tuple[str, str, str], Tuple[str, str, str, Any, Any, Any]]


def _template_text(template) -> str:
    if template is None:
        return DEFAULT_SXM_HEADER
    if hasattr(template, 'header_bytes') and getattr(template, 'filetype', None) == 'scan':
        return _header_text(template.header_bytes)
    if isinstance(template, (str, os.PathLike)):
        from ..parsers.scan import Scan   # local import avoids a cycle
        return _header_text(Scan(str(template)).header_bytes)
    raise TypeError(
        f"template must be None, a Scan or a path to an .sxm file, "
        f"got {type(template).__name__}"
    )


def _pair(value, what: str, positive: bool = False) -> Tuple[float, float]:
    try:
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be two numbers, got {value!r}") from None
    if arr.size != 2:
        raise ValueError(f"{what} must be two numbers, got {value!r}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{what} must be finite, got {value!r}")
    if positive and not np.all(arr > 0):
        raise ValueError(f"{what} must be positive, got {value!r}")
    return float(arr[0]), float(arr[1])


def _finite(value, what: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{what} must be a number, got {value!r}") from None
    if not np.isfinite(out):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return out


def _table_rows(lines: List[str]) -> List[List[str]]:
    return [line.strip('\t').split('\t') for line in lines if line.startswith('\t')]


def _resolve_channels(channels, template_rows) -> List[List[str]]:
    """Return DATA_INFO rows [Channel, Name, Unit, Direction, Calibration, Offset]."""
    tpl_by_name = {}
    if template_rows:
        cols = template_rows[0]
        for row in template_rows[1:]:
            rec = dict(zip(cols, row))
            if 'Name' in rec:
                tpl_by_name[rec['Name']] = rec

    if channels is None:
        if not tpl_by_name:
            raise ValueError("channels must be given (template has no DATA_INFO).")
        channels = [(r['Name'], r.get('Unit', ''), r.get('Direction', 'both'))
                    for r in tpl_by_name.values()]

    if len(channels) == 0:
        raise ValueError("channels must not be empty.")

    rows = []
    used_ids = set()
    seen = set()
    for spec in channels:
        if len(spec) not in (3, 6):
            raise ValueError(
                "Each channel must be (name, unit, direction) or "
                f"(name, unit, direction, channel_index, calibration, offset); got {spec!r}"
            )
        name = check_text_field(spec[0], 'Channel name')
        unit = check_text_field(spec[1], 'Channel unit')
        if not name.strip():
            raise ValueError("Channel names must not be empty.")
        if name in seen:
            raise ValueError(f"Channel '{name}' is listed twice.")
        seen.add(name)
        direction = str(spec[2]).strip().lower()
        if direction not in SCAN_DIRECTIONS:
            raise ValueError(
                f"Channel '{name}' has unknown direction {spec[2]!r}; "
                f"expected one of {sorted(SCAN_DIRECTIONS)}."
            )
        if len(spec) == 6:
            idx = str(int(spec[3]))
            cal = format_sci(_finite(spec[4], f"{name} calibration"), 3)
            off = format_sci(_finite(spec[5], f"{name} offset"), 3)
        elif name in tpl_by_name:
            rec = tpl_by_name[name]
            idx = rec.get('Channel', '')
            cal = rec.get('Calibration', '1.000E+0')
            off = rec.get('Offset', '0.000E+0')
        else:
            idx, cal, off = None, '1.000E+0', '0.000E+0'
        if idx is not None and idx.lstrip('-').isdigit():
            used_ids.add(int(idx))
        rows.append([idx, name, unit, direction, cal, off])

    # number new channels with free indices
    next_id = 0
    for row in rows:
        if row[0] is None:
            while next_id in used_ids:
                next_id += 1
            row[0] = str(next_id)
            used_ids.add(next_id)
    return rows


def _infer_pixels(signals: Mapping) -> Tuple[int, int]:
    for chan in signals.values():
        if isinstance(chan, Mapping):
            for arr in chan.values():
                shape = np.shape(arr)
                if len(shape) == 2:
                    return int(shape[1]), int(shape[0])
    raise ValueError("Cannot infer pixels from signals; pass pixels=(nx, ny).")


def _date_text(value) -> str:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime('%d.%m.%Y')
    text = str(value).strip()
    if not re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', text):
        raise ValueError(f"rec_date must be 'dd.mm.yyyy' or a date, got {value!r}")
    return text


def _time_text(value) -> str:
    if isinstance(value, (datetime.time, datetime.datetime)):
        return value.strftime('%H:%M:%S')
    text = str(value).strip()
    if not re.fullmatch(r'\d{2}:\d{2}:\d{2}', text):
        raise ValueError(f"rec_time must be 'HH:MM:SS' or a time, got {value!r}")
    return text


def _extra_value_lines(tag: str, value) -> List[str]:
    if isinstance(value, bool):
        lines = ['TRUE' if value else 'FALSE']
    elif isinstance(value, (int, float, np.integer, np.floating)):
        lines = [format_eng_exact(value)]
    elif isinstance(value, str):
        lines = value.split('\n')
    elif isinstance(value, (list, tuple)):
        lines = [str(v) for v in value]
    else:
        raise TypeError(f"extra_header['{tag}'] has unsupported type {type(value).__name__}")
    for line in lines:
        if '\r' in line or '\n' in line:
            raise ValueError(f"extra_header['{tag}'] lines must not contain line breaks")
        if _is_tag_line(line):
            raise ValueError(
                f"extra_header['{tag}'] value line {line!r} looks like a tag"
            )
    return lines


def write_sxm(
    fname,
    signals: Mapping,
    *,
    channels: Optional[Sequence[ChannelSpec]] = None,
    pixels: Optional[Tuple[int, int]] = None,
    scan_range: Optional[Tuple[float, float]] = None,
    scan_offset: Optional[Tuple[float, float]] = None,
    scan_angle: Optional[float] = None,
    scan_dir: Optional[str] = None,
    bias: Optional[float] = None,
    setpoint: Optional[Union[float, Tuple[float, str]]] = None,
    nanonis_version: Optional[int] = None,
    rec_date=None,
    rec_time=None,
    acq_time: Optional[float] = None,
    comment: Optional[str] = None,
    template=None,
    extra_header: Optional[Dict[str, Any]] = None,
    overwrite: bool = False,
) -> None:
    """
    Create a Nanonis .sxm file from arrays and scan parameters.

    The header is built from a template — a real .sxm (path or
    :class:`Scan`), or by default a built-in copy of a Nanonis Generic 5
    header — and every argument that is not None overrides the
    template's value. Arguments left as None keep the template's value
    (for the built-in template: 256×256-style FGT_0020 metadata, e.g.
    bias 10 mV, setpoint 50 pA, range 5 nm, angle 90°, scan_dir down).

    Data orientation follows :class:`Scan` exactly, with no flips: see
    the module docstring of :mod:`nanonispy2.writers.sxm` (line 0 is the
    first line acquired — top for ``down``, bottom for ``up`` — and
    backward lines run right to left).

    Parameters
    ----------
    fname : str or path-like
        Output path, must end with ``.sxm``.
    signals : mapping
        ``{channel name: {direction: (ny, nx) array}}``, the same
        structure ``Scan.signals`` has. A ``both`` channel needs
        ``'forward'`` and ``'backward'``; a single-direction channel
        needs exactly that direction. Use NaN for unmeasured lines of an
        aborted scan. Values are stored as big-endian float32.
    channels : sequence, optional
        ``(name, unit, direction)`` per channel in file order, with
        direction ``'both'``, ``'forward'`` or ``'backward'``. A 6-tuple
        ``(name, unit, direction, channel_index, calibration, offset)``
        also sets the DATA_INFO bookkeeping columns; otherwise they are
        taken from a template row of the same name, or set to a free
        index, 1.000E+0 and 0.000E+0. Nanonis itself writes names with
        underscores instead of spaces (``LI_Demod_1_X``). Default: the
        template's DATA_INFO.
    pixels : (int, int), optional
        ``(nx, ny)`` = (samples per line, lines). Default: inferred from
        the arrays.
    scan_range : (float, float), optional
        Frame size (width, height) in metres; finite and > 0.
    scan_offset : (float, float), optional
        Frame centre (x, y) in metres.
    scan_angle : float, optional
        Frame rotation in degrees.
    scan_dir : {'up', 'down'}, optional
    bias : float, optional
        Bias in volts (``:BIAS:`` and ``:Bias>Bias (V):``).
    setpoint : float or (float, str), optional
        Z-controller setpoint, optionally with its unit (default: the
        template's unit, ``A`` for the built-in template).
    nanonis_version : int, optional
        ``NANONIS_VERSION``. Versions < 2 store SCAN_PIXELS as
        ``ny nx``; this is handled for you. Default: the template's (2).
    rec_date : str or datetime.date, optional
        ``'dd.mm.yyyy'``.
    rec_time : str or datetime.time, optional
        ``'HH:MM:SS'``.
    acq_time : float, optional
        Acquisition time in seconds.
    comment : str, optional
        Free text; may span several lines, but no line may look like a
        header tag (``:...:``).
    template : str, path-like or Scan, optional
        Existing .sxm whose header supplies every entry not overridden.
    extra_header : dict, optional
        Additional or replacement header entries, ``{tag: value}``, e.g.
        ``{'Scan>series name': 'test_', 'REC_TEMP': '4.3'}``. Tags may
        be given with or without the surrounding colons. Values may be
        str (split on newlines), numbers (Nanonis engineering style),
        bool (TRUE/FALSE) or a list of lines. Tags that have a dedicated
        argument (BIAS, SCAN_RANGE, DATA_INFO, ...) are rejected.
    overwrite : bool, optional
        Replace an existing file. Default False.

    Notes
    -----
    ``SCANIT_TYPE`` is always ``FLOAT MSBFIRST``. ``SCAN_FILE``,
    ``NanonisMain>Session Path`` and ``Scan>series name`` are set from
    *fname* (override through *extra_header*). Mirrored entries
    (``Bias>Bias (V)``, ``Scan>Scanfield``, ``Scan>channels``,
    ``Scan>pixels/line``, ``Scan>lines``, ``Z-Controller>Setpoint``)
    are updated to match when present in the template; like Nanonis,
    they carry 6 significant digits. The fixed tags (BIAS, SCAN_RANGE,
    SCAN_OFFSET, SCAN_ANGLE, the Z-CONTROLLER setpoint, ACQ_TIME) use
    Nanonis' digit counts unless that would lose precision, in which
    case more digits are written so that they read back exactly.

    Examples
    --------
    >>> import numpy as np
    >>> from nanonispy2 import write_sxm
    >>> z = np.random.rand(23, 37)
    >>> write_sxm('demo.sxm', {'Z': {'forward': z, 'backward': z[:, ::-1]}},
    ...           channels=[('Z', 'm', 'both')], scan_range=(10e-9, 6e-9),
    ...           scan_dir='up', scan_angle=30, bias=-0.5, setpoint=100e-12)
    """
    check_target(fname, '.sxm', overwrite)
    if not isinstance(signals, Mapping):
        raise TypeError("signals must be a dict of {channel: {direction: array}}")

    text = _template_text(template)
    blocks = split_header_blocks(text)
    tpl = parse_scan_header(text + END_TAG + '\n')

    # ---- resolve and validate arguments
    tpl_version = 2
    try:
        tpl_version = int(str(tpl.get('nanonis_version', '2')).strip())
    except ValueError:
        pass
    version = tpl_version if nanonis_version is None else nanonis_version
    if isinstance(version, bool) or not isinstance(version, (int, np.integer)) or version < 1:
        raise ValueError(f"nanonis_version must be a positive int, got {nanonis_version!r}")

    dinfo = _find(blocks, 'DATA_INFO')
    rows = _resolve_channels(channels, _table_rows(dinfo[1]) if dinfo else None)

    if pixels is None:
        nx, ny = _infer_pixels(signals)
    else:
        if len(pixels) != 2:
            raise ValueError(f"pixels must be (nx, ny), got {pixels!r}")
        nx, ny = pixels
        if int(nx) != nx or int(ny) != ny:
            raise ValueError(f"pixels must be integers, got {pixels!r}")
        nx, ny = int(nx), int(ny)
    if nx < 1 or ny < 1:
        raise ValueError(f"pixels must be >= 1, got {(nx, ny)}")

    rng = _pair(scan_range, 'scan_range', positive=True) if scan_range is not None else None
    off = _pair(scan_offset, 'scan_offset') if scan_offset is not None else None
    ang = _finite(scan_angle, 'scan_angle') if scan_angle is not None else None
    if scan_dir is not None:
        direction = str(scan_dir).strip().lower()
        if direction not in ('up', 'down'):
            raise ValueError(f"scan_dir must be 'up' or 'down', got {scan_dir!r}")
    bias_v = _finite(bias, 'bias') if bias is not None else None
    if setpoint is not None:
        if isinstance(setpoint, (tuple, list)):
            if len(setpoint) != 2:
                raise ValueError(f"setpoint must be value or (value, unit), got {setpoint!r}")
            sp_value = _finite(setpoint[0], 'setpoint')
            sp_unit = check_text_field(setpoint[1], 'setpoint unit')
        else:
            sp_value, sp_unit = _finite(setpoint, 'setpoint'), None
    if acq_time is not None:
        acq = _finite(acq_time, 'acq_time')
        if acq < 0:
            raise ValueError(f"acq_time must be >= 0, got {acq_time!r}")
    if comment is not None:
        comment_lines = str(comment).replace('\r\n', '\n').split('\n')
        for line in comment_lines:
            if line.startswith(':'):
                raise ValueError(
                    f"comment line {line!r} starts with ':' and would be read "
                    "as a header tag"
                )

    # ---- fixed tags
    _set(blocks, 'NANONIS_VERSION', [str(int(version))])
    _set(blocks, 'SCANIT_TYPE', [SCANIT_TYPE_LINE])
    if rec_date is not None:
        _set(blocks, 'REC_DATE', [' ' + _date_text(rec_date)])
    if rec_time is not None:
        _set(blocks, 'REC_TIME', [_time_text(rec_time)])
    if acq_time is not None:
        _set(blocks, 'ACQ_TIME', [format_fixed(acq, 1).rjust(12)])
    first, second = (nx, ny) if version >= 2 else (ny, nx)
    _set(blocks, 'SCAN_PIXELS', [f'{first:>10d}{second:>10d}'])
    _set(blocks, 'SCAN_FILE', [os.path.abspath(str(fname))])
    if rng is not None:
        _set(blocks, 'SCAN_RANGE', [''.join(format_sci(v, 6).rjust(22) for v in rng)])
    if off is not None:
        _set(blocks, 'SCAN_OFFSET',
             [format_sci(off[0], 6).rjust(24) + format_sci(off[1], 6).rjust(20)])
    if ang is not None:
        _set(blocks, 'SCAN_ANGLE', [format_sci(ang, 3).rjust(20)])
    if scan_dir is not None:
        _set(blocks, 'SCAN_DIR', [direction])
    if bias_v is not None:
        _set(blocks, 'BIAS', [format_sci(bias_v, 6)])
    if setpoint is not None:
        _set_setpoint(blocks, sp_value, sp_unit)
    if comment is not None:
        _set(blocks, 'COMMENT', comment_lines)
    _set(blocks, 'DATA_INFO',
         ['\t' + '\t'.join(_DATA_INFO_COLUMNS)]
         + ['\t' + '\t'.join(row) for row in rows] + [''])

    # ---- mirrored Section>Key entries
    stem = Path(str(fname)).stem
    _set_if_present(blocks, 'NanonisMain>Session Path',
                    [os.path.dirname(os.path.abspath(str(fname)))])
    _set_if_present(blocks, 'Scan>series name', [re.sub(r'\d+$', '', stem)])
    _set_if_present(blocks, 'Scan>pixels/line', [str(nx)])
    _set_if_present(blocks, 'Scan>lines', [str(ny)])
    # Section>Key mirrors use Nanonis' 6 significant digits; the fixed
    # tags above are the authoritative (exact) values
    if bias_v is not None:
        _set_if_present(blocks, 'Bias>Bias (V)', [format_eng(bias_v, 6, strip=True)])
    if rng is not None or off is not None or ang is not None:
        new = parse_scan_header(render_header_blocks(blocks) + END_TAG + '\n')
        if all(k in new for k in ('scan_offset', 'scan_range', 'scan_angle')):
            field = list(new['scan_offset']) + list(new['scan_range']) \
                + [float(new['scan_angle'])]
            _set_if_present(blocks, 'Scan>Scanfield',
                            [';'.join(format_eng(v, 6, strip=True) for v in field)])
    if channels is not None:
        _set_if_present(blocks, 'Scan>channels',
                        [';'.join(f"{r[1].replace('_', ' ')} ({r[2]})" for r in rows)])

    # ---- user extras
    for key, value in (extra_header or {}).items():
        tag = check_text_field(str(key).strip(), 'extra_header tag', allow_tab=False)
        if tag.startswith(':') and tag.endswith(':') and len(tag) >= 2:
            tag = tag[1:-1]
        if not tag:
            raise ValueError("extra_header tags must not be empty")
        if tag in _ARG_TAGS:
            raise ValueError(
                f"extra_header may not set '{tag}'; use the corresponding "
                "write_sxm argument instead."
            )
        _set(blocks, tag, _extra_value_lines(tag, value))

    write_scan_file(fname, render_header_blocks(blocks), signals, overwrite=overwrite)


def _set_setpoint(blocks: List[Block], value: float, unit: Optional[str]) -> None:
    """Update the Z-CONTROLLER table and the Z-Controller>Setpoint mirrors."""
    block = _find(blocks, 'Z-CONTROLLER')
    if block is None:
        _set(blocks, 'Z-CONTROLLER', [
            '\tName\ton\tSetpoint\tP-gain\tI-gain\tT-const',
            '\tlog Current\t1\t5.000E-11 A\t0.000E+0 m\t1.000E-8 m/s\t0.000E+0 s',
        ])
        block = _find(blocks, 'Z-CONTROLLER')
    lines = block[1]
    table = [i for i, line in enumerate(lines) if line.startswith('\t')]
    if len(table) < 2:
        raise ValueError("Template Z-CONTROLLER table has no data row.")
    header = lines[table[0]].strip('\t').split('\t')
    if 'Setpoint' not in header:
        raise ValueError("Template Z-CONTROLLER table has no Setpoint column.")
    col = header.index('Setpoint')
    cells = lines[table[1]].strip('\t').split('\t')
    old = cells[col].split(None, 1) if col < len(cells) else []
    if unit is None:
        unit = old[1] if len(old) == 2 else 'A'
    while len(cells) <= col:
        cells.append('')
    cells[col] = f'{format_sci(value, 3)} {unit}'.rstrip()
    lines[table[1]] = '\t' + '\t'.join(cells)
    _set_if_present(blocks, 'Z-Controller>Setpoint', [format_eng(value, 6, strip=True)])
    _set_if_present(blocks, 'Z-Controller>Setpoint unit', [unit])


__all__ = [
    'write_sxm',
    'write_scan_file',
    'header_to_bytes',
    'split_header_blocks',
    'render_header_blocks',
    'stack_scan_frames',
]
