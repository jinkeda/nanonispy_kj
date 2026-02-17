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

## Architecture

```
nanonispy2/
├── __init__.py          # Public API: Grid, Scan, Spec
├── constants.py         # Format dicts and end tags
├── read.py              # Backward-compat shim (deprecated)
├── core/
│   ├── base.py          # NanonisFile base class
│   ├── exceptions.py    # Custom exception hierarchy
│   └── validators.py    # Input validation utilities
├── io/
│   ├── binary.py        # BinaryReader for binary data
│   └── formats.py       # Data format registry
└── parsers/
    ├── header.py        # Header parsing (3ds, sxm, dat)
    ├── grid.py          # Grid class
    ├── scan.py          # Scan class
    └── spec.py          # Spec class
```

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
