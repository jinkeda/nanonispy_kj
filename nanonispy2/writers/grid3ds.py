"""
Builder for Nanonis grid spectroscopy (.3ds) files from scratch.

Layout (verified on a Nanonis Generic 5 linear bias grid):

- CRLF-terminated ``key=value`` header lines in the order
  ``Grid dim``, ``Grid settings``, ``Filetype``, ``Sweep Signal``,
  ``Fixed parameters``, ``Experiment parameters``,
  ``# Parameters (4 byte)``, ``Experiment size (bytes)``, ``Points``,
  ``Channels``, ``Delay before measuring (s)``, ``Experiment``,
  ``Start time``, ``End time``, ``User``, ``Comment``, then
  ``:HEADER_END:``.
- Big-endian float32 data, pixel by pixel (ny × nx, as returned by
  :class:`Grid`), each pixel holding the parameters
  ``[Sweep Start, Sweep End, *experiment parameters]`` followed by each
  channel's sweep.

Not supported: non-linear sweeps (``Filetype`` other than ``Linear``),
backward sweeps and their ``[bwd]`` channel naming, and incomplete
grids — no real file with those was available to verify the format.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional, Tuple

import numpy as np

from .common import check_target, check_text_field
from .numfmt import format_sci

GRID_DTYPE = np.dtype('>f4')


def _quoted(value: str, what: str) -> str:
    value = check_text_field(value, what)
    if '"' in value:
        raise ValueError(f"{what} must not contain '\"': {value!r}")
    return f'"{value}"'


def _names(names, what: str) -> str:
    out = []
    for name in names:
        name = check_text_field(name, what)
        if not name or ';' in name or '"' in name:
            raise ValueError(f"{what} {name!r} must be non-empty without ';' or '\"'")
        out.append(name)
    return _quoted(';'.join(out), what)


def write_3ds(
    fname,
    signals: Mapping,
    *,
    sweep_start: float,
    sweep_end: float,
    grid_center: Tuple[float, float] = (0.0, 0.0),
    grid_size: Tuple[float, float],
    grid_angle: float = 0.0,
    sweep_signal: str = 'Bias (V)',
    experiment_parameters: Optional[Dict[str, Any]] = None,
    measure_delay: float = 0.0,
    experiment: str = 'Grid Spectroscopy',
    start_time: str = '',
    end_time: str = '',
    user: str = '',
    comment: str = '',
    overwrite: bool = False,
) -> None:
    """
    Create a Nanonis grid spectroscopy (.3ds) file from scratch.

    Parameters
    ----------
    fname : str or path-like
        Output path, must end with ``.3ds``.
    signals : dict
        ``{channel name: (ny, nx, points) array}``, the layout
        ``Grid.signals`` uses (e.g. ``'Current (A)'``). Grid dimensions
        and sweep points are taken from the arrays.
    sweep_start, sweep_end : float
        Sweep endpoints; stored per pixel as the fixed parameters
        ``Sweep Start``/``Sweep End``. :class:`Grid` rebuilds the sweep
        as ``linspace(sweep_start, sweep_end, points)``.
    grid_center : (float, float), optional
        Frame centre (x, y) in metres. Default (0, 0).
    grid_size : (float, float)
        Frame size (width, height) in metres; finite and > 0.
    grid_angle : float, optional
        Frame rotation in degrees. Default 0.
    sweep_signal : str, optional
        Default ``'Bias (V)'``.
    experiment_parameters : dict, optional
        ``{label: (ny, nx) array}`` per-pixel parameters in order, e.g.
        ``{'X (m)': x, 'Y (m)': y, 'Z (m)': z}``. ``Grid.signals['topo']``
        is the ``Z (m)`` entry. Default ``{'Z (m)': zeros}``.
    measure_delay : float, optional
        ``Delay before measuring (s)``. Default 0.
    experiment, start_time, end_time, user, comment : str, optional
        Metadata. Times are ``'dd.mm.yyyy HH:MM:SS'`` in real files.
    overwrite : bool, optional
        Replace an existing file. Default False.

    Examples
    --------
    >>> import numpy as np
    >>> from nanonispy2 import write_3ds
    >>> cur = np.random.rand(16, 20, 101) * 1e-9      # (ny, nx, points)
    >>> write_3ds('demo.3ds', {'Current (A)': cur}, sweep_start=-0.1,
    ...           sweep_end=0.1, grid_size=(20e-9, 16e-9))
    """
    check_target(fname, '.3ds', overwrite)
    if not isinstance(signals, Mapping) or len(signals) == 0:
        raise ValueError("signals must be a non-empty dict of channel -> (ny, nx, points) array")

    arrays = {k: np.asarray(v) for k, v in signals.items()}
    shapes = {k: a.shape for k, a in arrays.items()}
    first = next(iter(shapes.values()))
    if len(first) != 3 or any(s != first for s in shapes.values()):
        raise ValueError(f"All channels must be (ny, nx, points) arrays of one shape, got {shapes}")
    ny, nx, npts = first
    if min(ny, nx, npts) < 1:
        raise ValueError(f"Grid arrays must not be empty, got shape {first}")

    if experiment_parameters is None:
        experiment_parameters = {'Z (m)': np.zeros((ny, nx))}
    params = {k: np.asarray(v) for k, v in experiment_parameters.items()}
    bad = {k: p.shape for k, p in params.items() if p.shape != (ny, nx)}
    if bad:
        raise ValueError(f"experiment_parameters must be (ny, nx) = {(ny, nx)} arrays, got {bad}")
    if len(params) == 0:
        raise ValueError("experiment_parameters must not be empty")

    numbers = [sweep_start, sweep_end, grid_angle, measure_delay]
    size = np.asarray(grid_size, dtype=np.float64).reshape(-1)
    center = np.asarray(grid_center, dtype=np.float64).reshape(-1)
    if size.size != 2 or center.size != 2:
        raise ValueError("grid_size and grid_center must be two numbers each")
    if not np.all(np.isfinite(np.r_[size, center, numbers])):
        raise ValueError("grid geometry, sweep endpoints and delay must be finite")
    if not np.all(size > 0):
        raise ValueError(f"grid_size must be positive, got {grid_size!r}")

    channels = list(arrays)
    fixed = ['Sweep Start', 'Sweep End']
    num_param = len(fixed) + len(params)
    settings = ';'.join(format_sci(v, 6) for v in
                        [center[0], center[1], size[0], size[1], grid_angle])
    lines = [
        f'Grid dim="{nx} x {ny}"',
        f'Grid settings={settings}',
        'Filetype=Linear',
        f"Sweep Signal={_quoted(sweep_signal, 'sweep_signal')}",
        f"Fixed parameters={_names(fixed, 'Fixed parameter')}",
        f"Experiment parameters={_names(params, 'Experiment parameter')}",
        f'# Parameters (4 byte)={num_param}',
        f'Experiment size (bytes)={4 * npts * len(channels)}',
        f'Points={npts}',
        f"Channels={_names(channels, 'Channel')}",
        f'Delay before measuring (s)={format_sci(measure_delay, 6)}',
        f"Experiment={_quoted(experiment, 'experiment')}",
        f"Start time={_quoted(start_time, 'start_time')}",
        f"End time={_quoted(end_time, 'end_time')}",
        f"User={check_text_field(user, 'user')}",
        f"Comment={check_text_field(comment, 'comment')}",
        ':HEADER_END:',
    ]
    for name, value in (('user', user), ('comment', comment)):
        if ';' in str(value):
            raise ValueError(f"{name} must not contain ';' (it would be read as a list)")
    header = ('\r\n'.join(lines) + '\r\n').encode('utf-8')

    data = np.empty((ny, nx, num_param + npts * len(channels)), dtype=GRID_DTYPE)
    data[:, :, 0] = sweep_start
    data[:, :, 1] = sweep_end
    for i, p in enumerate(params.values()):
        data[:, :, 2 + i] = p
    for i, name in enumerate(channels):
        start = num_param + i * npts
        data[:, :, start:start + npts] = arrays[name]

    with open(fname, 'wb') as fh:
        fh.write(header)
        data.tofile(fh)


__all__ = ['write_3ds']
