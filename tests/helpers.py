"""
Test comparison helpers for nanonispy2.

Provides reusable assertion functions that compare data objects
using appropriate tolerances for scientific floating-point data.
"""

import numpy as np
import numpy.testing as npt


# Default tolerances
FLOAT64_RTOL = 1e-7
FLOAT32_RTOL = 1e-5
DEFAULT_ATOL = 0


def normalize_header_dict(d):
    """
    Normalize a header dictionary for stable comparison.

    Strips whitespace from string values, lowercases keys,
    and sorts any list values.

    Parameters
    ----------
    d : dict
        Header dictionary to normalize.

    Returns
    -------
    dict
        Normalized copy.
    """
    normalized = {}
    for key, val in d.items():
        norm_key = key.strip().lower()
        if isinstance(val, str):
            norm_val = val.strip()
        elif isinstance(val, list):
            norm_val = sorted(val) if all(isinstance(v, str) for v in val) else val
        else:
            norm_val = val
        normalized[norm_key] = norm_val
    return normalized


def assert_array_close(actual, expected, name="array", rtol=None, atol=DEFAULT_ATOL):
    """
    Assert two arrays are close, with named context for error messages.

    Automatically selects tolerance based on dtype if rtol is not specified.

    Parameters
    ----------
    actual : array_like
        Actual values.
    expected : array_like
        Expected values.
    name : str
        Name for error context.
    rtol : float, optional
        Relative tolerance. Auto-detected from dtype if None.
    atol : float
        Absolute tolerance.
    """
    actual = np.asarray(actual)
    expected = np.asarray(expected)

    if rtol is None:
        # Choose rtol based on the less precise dtype
        if actual.dtype == np.float32 or expected.dtype == np.float32:
            rtol = FLOAT32_RTOL
        else:
            rtol = FLOAT64_RTOL

    npt.assert_allclose(
        actual, expected, rtol=rtol, atol=atol,
        err_msg=f"Mismatch in '{name}'"
    )


def assert_grid_equivalent(old, new):
    """
    Assert two Grid objects produce equivalent results.

    Compares header fields, channel lists, and signal arrays.

    Parameters
    ----------
    old : Grid
        Reference Grid object.
    new : Grid
        New Grid object to compare against.
    """
    # Header fields
    assert old.header['dim_px'] == new.header['dim_px'], "dim_px mismatch"
    assert old.header['num_sweep_signal'] == new.header['num_sweep_signal'], \
        "num_sweep_signal mismatch"
    assert old.header['num_parameters'] == new.header['num_parameters'], \
        "num_parameters mismatch"
    assert old.header['channels'] == new.header['channels'], "channels mismatch"
    assert old.header['num_channels'] == new.header['num_channels'], \
        "num_channels mismatch"

    # Signal arrays
    for key in old.signals:
        assert key in new.signals, f"Missing signal key '{key}'"
        assert_array_close(
            new.signals[key], old.signals[key],
            name=f"signals['{key}']"
        )


def assert_scan_equivalent(old, new):
    """
    Assert two Scan objects produce equivalent results.

    Parameters
    ----------
    old : Scan
        Reference Scan object.
    new : Scan
        New Scan object to compare against.
    """
    # Header fields
    npt.assert_array_equal(
        old.header['scan_pixels'], new.header['scan_pixels'],
        err_msg="scan_pixels mismatch"
    )

    # Channels
    old_channels = list(old.signals.keys())
    new_channels = list(new.signals.keys())
    assert old_channels == new_channels, \
        f"Channel lists differ: {old_channels} vs {new_channels}"

    # Signal arrays
    for ch in old_channels:
        for direction in ('forward', 'backward'):
            assert_array_close(
                new.signals[ch][direction],
                old.signals[ch][direction],
                name=f"signals['{ch}']['{direction}']"
            )


def assert_spec_equivalent(old, new):
    """
    Assert two Spec objects produce equivalent results.

    Parameters
    ----------
    old : Spec
        Reference Spec object.
    new : Spec
        New Spec object to compare against.
    """
    old_keys = list(old.signals.keys())
    new_keys = list(new.signals.keys())
    assert old_keys == new_keys, f"Column name lists differ: {old_keys} vs {new_keys}"

    for key in old_keys:
        assert_array_close(
            new.signals[key], old.signals[key],
            name=f"signals['{key}']"
        )
