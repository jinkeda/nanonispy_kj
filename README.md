# nanonispy2

Python library for reading and writing [Nanonis](https://www.specs-group.com/nanonis/) SPM data files.

Supports `.3ds` (grid spectroscopy), `.sxm` (scan), and `.dat` (point spectroscopy) formats.

## Installation

```bash
pip install -e .
```

For development tools (pytest, ruff, mypy):

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from nanonispy2 import Grid, Scan, Spec

# Grid spectroscopy (.3ds)
grid = Grid("path/to/file.3ds")
grid.header          # parsed header dict
grid.signals         # channel data (dict of 3D arrays)
grid.signals['topo'] # topographic map (Z-height at each pixel)

# Scan image (.sxm)
scan = Scan("path/to/file.sxm")
scan.signals['Z']['forward']   # forward scan image
scan.signals['Z']['backward']  # backward scan image

# Point spectroscopy (.dat)
spec = Spec("path/to/file.dat")
spec.signals  # dict of 1D arrays, one per column
```

## Writing

All three formats can be written back from a loaded file (`Grid.write`,
`Scan.write`, `Spec.write`) or created from scratch (`write_3ds`,
`write_sxm`, `write_dat`). All writers:

- refuse a wrong extension (`UnhandledFileError`);
- refuse to replace an existing file unless `overwrite=True`;
- check that the header matches the data before anything is written (`ValueError`).

Writing a loaded file back unchanged reproduces it **byte for byte** (verified on
the example `.sxm`, `.dat` and `.3ds` files).

### Rewriting loaded files

```python
grid = Grid("input.3ds")
grid.signals['Current (A)'] *= 2.0
grid.write("output.3ds")                    # overwrite=True to replace

scan = Scan("input.sxm")
scan.signals['Z']['forward'] = scan.signals['Z']['forward'] - 1e-9
scan.write("output.sxm")                    # big-endian float32, exact

spec = Spec("input.dat")
spec.signals['Current (A)'] = spec.signals['Current (A)'] * 2
spec.header['User'] = 'me'                  # changed header entries are re-rendered
spec.write("output.dat")                    # precision=8 (Nanonis style) by default
```

### Creating `.sxm` scans

```python
import numpy as np
from nanonispy2 import write_sxm

ny, nx = 23, 37
z = np.random.rand(ny, nx) * 1e-10
write_sxm(
    "synthetic_001.sxm",
    {'Z':       {'forward': z, 'backward': z[:, ::-1]},
     'Current': {'forward': np.full((ny, nx), 5e-11)}},
    channels=[('Z', 'm', 'both'), ('Current', 'A', 'forward')],
    scan_range=(10e-9, 6e-9), scan_offset=(0, 0), scan_angle=30,
    scan_dir='up', bias=-0.5, setpoint=100e-12,
    rec_date='01.01.2026', rec_time='12:00:00', acq_time=60.0,
    comment='synthetic test scan',
)
```

- `signals` has the same structure as `Scan.signals`: one `(ny, nx)` array per
  recorded direction. `both` channels need `forward` and `backward`, while
  single-direction channels need exactly that one.
- **Orientation:** arrays are written in the raw order `Scan` returns them, with no
  flips. Line 0 is the first line acquired: the top of the frame for
  `scan_dir='down'` and the bottom for `'up'`. Backward lines are stored in
  acquisition order, i.e. right to left.
- Unmeasured lines of an aborted scan are NaN and are written as-is.
- The header comes from a **template**. By default this is a built-in copy of a
  Nanonis Generic 5 header; alternatively pass `template="real.sxm"` or a `Scan`.
  Every argument left as `None` keeps the template's value. `extra_header={...}`
  adds or replaces any other entry, e.g. `{'Scan>series name': 'synthetic_'}`.
- `nanonis_version=1` writes the old `ny nx` order of `SCAN_PIXELS`. `Scan` reads
  either version back as `[nx, ny]`.
- Header numbers use Nanonis' digit counts (`5.000000E-9`). If that would lose
  precision, more digits are written, so values always read back exactly.
  Mirrored `Section>Key` entries keep Nanonis' 6 significant digits.

### Creating `.dat` spectra

```python
from nanonispy2 import write_dat

v = np.linspace(-0.1, 0.1, 201)
write_dat(
    "synthetic_00001.dat",
    {'Bias calc (V)': v, 'Current (A)': 1e-9 * np.tanh(10 * v)},
    {'Saved Date': '01.01.2026 12:00:00', 'X (m)': 0.0, 'Z-Ctrl hold': True},
)
```

The writer produces CRLF line endings and `key<TAB>value<TAB>` header lines, with
`Experiment` (default `bias spectroscopy`) written first. Data use Nanonis
engineering notation with **8 significant digits** (`-146.39633E-9`), and missing
values are written as `NaN`.

8 digits give a relative error of up to 5e-8, which is not lossless:
float32 needs 9 digits to round-trip exactly and float64 up to 17. Pass
`precision=None` to write the shortest representation that reads back as the
identical float64.

### Creating `.3ds` grids

```python
from nanonispy2 import write_3ds

cur = np.random.rand(16, 20, 101) * 1e-9          # (ny, nx, points)
write_3ds("synthetic.3ds", {'Current (A)': cur},
          sweep_start=-0.1, sweep_end=0.1,
          grid_center=(0, 0), grid_size=(20e-9, 16e-9), grid_angle=0,
          experiment_parameters={'Z (m)': np.zeros((16, 20))})
```

### Not supported

The example files contain none of the following, so their format could not be
verified, and the writers do not invent it:

- backward sweeps (`[bwd]` columns/channels) in `.dat` and `.3ds`;
- non-linear (`Filetype` other than `Linear`) or incomplete grids;
- little-endian `.sxm` data.

## .3ds File Format

A Nanonis `.3ds` file stores grid spectroscopy data — a spectrum is recorded at every pixel of a 2D grid. The file has two sections:

### Header (ASCII)

The header is plain text, terminated by `\r\n:HEADER_END:\r\n`. It contains key-value pairs describing the experiment:

| Header key | Meaning | Example |
|---|---|---|
| `Grid dim` | Grid size in pixels (nx × ny) | `64 x 64` |
| `Grid settings` | Center position, size, angle | `0;0;1e-6;1e-6;0` |
| `Sweep Signal` | What is swept per pixel | `Bias (V)` |
| `Fixed parameters` | Parameters fixed during sweep | `X (m);Y (m)` |
| `Experimental parameters` | Parameters recorded per pixel | `Z (m)` |
| `# Parameters (4 byte)` | Number of parameters stored per pixel | `1` |
| `Experiment size (bytes)` | Sweep points per channel | `512` |
| `Channels` | Recorded signal channels | `Current (A)` |

### Binary Data

After the header, data is stored as **big-endian 32-bit floats** (by default), organized pixel by pixel:

```
Pixel (0,0): [param₁ … paramₙ] [chan₁_sweep₁ … chan₁_sweepₛ] [chan₂_sweep₁ … chan₂_sweepₛ] …
Pixel (1,0): [param₁ … paramₙ] [chan₁_sweep₁ … chan₁_sweepₛ] [chan₂_sweep₁ … chan₂_sweepₛ] …
…
Pixel (nx-1, ny-1): …
```

Each pixel contains:
1. **Parameters** (`num_parameters` values) — experimental conditions at that pixel (e.g. Z-height)
2. **Channel data** — for each channel, `num_sweep_signal` values representing the spectroscopy curve

The total number of floats per pixel is: `num_parameters + num_channels × num_sweep_signal`

### Mapping to Python

```python
grid = Grid("file.3ds")

grid.header['dim_px']           # [nx, ny] — grid dimensions
grid.header['channels']         # ['Current (A)', ...] — channel names
grid.header['num_sweep_signal'] # 512 — points per sweep
grid.header['num_parameters']   # 1 — parameters per pixel

grid.signals['params']          # shape (ny, nx, num_parameters)
grid.signals['Current (A)']     # shape (ny, nx, num_sweep_signal)
grid.signals['sweep_signal']    # 1D bias array, length num_sweep_signal
grid.signals['topo']            # shape (ny, nx) — Z-height map
```

## Architecture

```
nanonispy2/
├── __init__.py          # Public API: Grid, Scan, Spec, write_sxm, write_dat, write_3ds
├── py.typed             # PEP 561 marker for type checkers
├── read.py              # Backward-compat shim (deprecated)
├── core/
│   ├── base.py          # NanonisFile base class (pathlib-based)
│   ├── exceptions.py    # Custom exception hierarchy
│   └── validators.py    # Input validation (file path, headers)
├── io/
│   ├── binary.py        # BinaryReader (deprecated, will be removed)
│   └── formats.py       # Data format registry
├── parsers/
│   ├── header.py        # Header parsing (3ds, sxm, dat)
│   ├── types.py         # TypedDict definitions for headers
│   ├── grid.py          # Grid class
│   ├── scan.py          # Scan class
│   └── spec.py          # Spec class
└── writers/
    ├── numfmt.py        # Nanonis number formatting
    ├── sxm.py           # write_sxm + Scan.write back end
    ├── _sxm_default.py  # Built-in .sxm header template
    ├── dat.py           # write_dat + Spec.write back end
    └── grid3ds.py       # write_3ds
```

## Error Handling

The library raises specific exceptions for common issues:

| Exception | When |
|---|---|
| `UnhandledFileError` | Wrong file extension |
| `FileHeaderNotFoundError` | Header end tag missing |
| `CorruptedDataError` | Truncated or corrupt binary data |
| `MissingHeaderEntryError` | Required header field missing |
| `InvalidDataFormatError` | Unrecognized data format |

Truncated grid files emit a warning and zero-fill missing data.
Truncated scan files raise `CorruptedDataError` with a clear message.
Scans that mix `both` and single-direction channels are read correctly;
`scan.signals[ch]` contains only the directions recorded for that channel.

## Running Tests

```bash
python -m pytest tests/ -v
```

`tests/test_writers.py` covers the writers. It checks:

- byte-identical rewrites of the real files;
- round trips after modifying data;
- `.sxm` scans created from scratch (up/down, several angles, odd and non-square
  sizes, mixed directions, NaN lines, version 1);
- `.dat` and `.3ds` files created from scratch;
- error handling.

Tests require real Nanonis data files in `nano_spec/data/`. If the test data directory is missing, data-dependent tests are skipped gracefully.

## Migration from `nanonispy2.read`

The legacy `nanonispy2.read` module is deprecated. Update your imports:

```python
# Old (still works, emits FutureWarning)
from nanonispy2.read import Grid

# New
from nanonispy2 import Grid
```

## License

See [LICENSE](LICENSE) for details.
