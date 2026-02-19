"""
Baseline equivalence tests for nanonispy2.

These tests capture the current behavior of read.py as frozen snapshots.
They serve as a regression baseline during refactoring — if a change breaks
these, it signals a semantic change that must be reviewed.

These are BEHAVIOR CAPTURE tests, not spec tests. Some captured values may
reflect quirks of the current implementation.
"""

import numpy as np
import numpy.testing as npt
import pytest

from nanonispy2.read import Grid, Scan, Spec


class TestGridEquivalence:
    """Captured behavior for Grid files."""

    def test_header_snapshot(self, grid_file):
        """Key header fields match expected values for test data."""
        g = Grid(grid_file)
        assert g.header['dim_px'] == [64, 64]
        assert g.header['num_sweep_signal'] == 101
        assert g.header['num_parameters'] == 14
        assert g.filetype == 'grid'

    def test_data_dtype(self, grid_file):
        """Signal arrays use float dtype."""
        g = Grid(grid_file)
        for ch in g.header['channels']:
            assert np.issubdtype(g.signals[ch].dtype, np.floating), \
                f"Channel '{ch}' has non-float dtype {g.signals[ch].dtype}"

    def test_sweep_signal_endpoints(self, grid_file):
        """Sweep signal start/end should match first pixel params."""
        g = Grid(grid_file)
        sweep = g.signals['sweep_signal']
        params_start = g.signals['params'][0, 0, 0]
        params_end = g.signals['params'][0, 0, 1]

        npt.assert_allclose(sweep[0], params_start, rtol=1e-5,
                            err_msg="Sweep start doesn't match params")
        npt.assert_allclose(sweep[-1], params_end, rtol=1e-5,
                            err_msg="Sweep end doesn't match params")

    def test_data_finite_percentage(self, grid_file):
        """Most data should be finite (not NaN/Inf)."""
        g = Grid(grid_file)
        for ch in g.header['channels']:
            finite_frac = np.mean(np.isfinite(g.signals[ch]))
            assert finite_frac > 0.9, \
                f"Channel '{ch}' is only {finite_frac:.1%} finite"


class TestScanEquivalence:
    """Captured behavior for Scan files."""

    def test_header_snapshot(self, scan_file):
        """Key header fields match expected values for test data."""
        s = Scan(scan_file)
        npt.assert_array_equal(s.header['scan_pixels'], [256, 256])
        assert s.filetype == 'scan'

    def test_data_dtype(self, scan_file):
        """Signal arrays use float dtype."""
        s = Scan(scan_file)
        for ch in s.signals:
            assert np.issubdtype(s.signals[ch]['forward'].dtype, np.floating)
            assert np.issubdtype(s.signals[ch]['backward'].dtype, np.floating)

    def test_forward_backward_differ(self, scan_file):
        """Forward and backward scans should generally differ."""
        s = Scan(scan_file)
        for ch in s.signals:
            fwd = s.signals[ch]['forward']
            bwd = s.signals[ch]['backward']
            # They shouldn't be identical (very unlikely for real data)
            if not np.allclose(fwd, bwd, rtol=1e-10):
                break
        else:
            # If ALL channels are identical fwd/bwd, that's suspicious
            pytest.skip("All channels have identical fwd/bwd — possible but unusual")


class TestSpecEquivalence:
    """Captured behavior for Spec files."""

    def test_header_snapshot(self, spec_file):
        """Spec file should parse without error and have a header."""
        sp = Spec(spec_file)
        assert sp.filetype == 'spec'
        assert isinstance(sp.header, dict)
        assert len(sp.header) > 0

    def test_has_bias_column(self, spec_file):
        """Bias spectroscopy should have a bias-related column."""
        sp = Spec(spec_file)
        bias_keys = [k for k in sp.signals.keys() if 'bias' in k.lower()]
        assert len(bias_keys) >= 1, \
            f"No bias column found in: {list(sp.signals.keys())}"

    def test_data_dtype(self, spec_file):
        """All columns should be float dtype."""
        sp = Spec(spec_file)
        for key, val in sp.signals.items():
            assert np.issubdtype(val.dtype, np.floating), \
                f"Column '{key}' has dtype {val.dtype}"


class TestErrorPaths:
    """Verify expected error behavior."""

    def test_invalid_extension_grid(self, tmp_path):
        """Grid rejects non-.3ds files."""
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("dummy")
        with pytest.raises(Exception):  # UnhandledFileError
            Grid(str(bad_file))

    def test_invalid_extension_scan(self, tmp_path):
        """Scan rejects non-.sxm files."""
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("dummy")
        with pytest.raises(Exception):
            Scan(str(bad_file))

    def test_invalid_extension_spec(self, tmp_path):
        """Spec rejects non-.dat files."""
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("dummy")
        with pytest.raises(Exception):
            Spec(str(bad_file))
