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

## Writing Grid Files

`Grid` supports writing back to `.3ds` format — useful for modifying signal data and re-exporting:

```python
grid = Grid("input.3ds")

# Modify existing channel data
grid.signals['Current (A)'] *= 2.0

# Write to a new file
grid.write("output.3ds")

# Overwrite an existing file
grid.write("output.3ds", overwrite=True)
```

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
├── __init__.py          # Public API: Grid, Scan, Spec
├── py.typed             # PEP 561 marker for type checkers
├── read.py              # Backward-compat shim (deprecated)
├── core/
│   ├── base.py          # NanonisFile base class (pathlib-based)
│   ├── exceptions.py    # Custom exception hierarchy
│   └── validators.py    # Input validation (file path, headers)
├── io/
│   ├── binary.py        # BinaryReader (deprecated, will be removed)
│   └── formats.py       # Data format registry
└── parsers/
    ├── header.py        # Header parsing (3ds, sxm, dat)
    ├── types.py         # TypedDict definitions for headers
    ├── grid.py          # Grid class
    ├── scan.py          # Scan class
    └── spec.py          # Spec class
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

## Running Tests

```bash
python -m pytest tests/ -v
```

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
