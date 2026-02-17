"""
Baseline invariant tests for nanonispy2.

These tests verify spec-level truths that must ALWAYS hold regardless of
implementation. They test structural consistency between headers and data,
not specific values.
"""

import numpy as np
import pytest

from nanonispy2.read import Grid, Scan, Spec


class TestGridInvariants:
    """Invariants that must hold for any valid grid file."""

    def test_signal_shapes_match_header(self, grid_file):
        """Each channel array shape must match (ny, nx, num_sweep)."""
        g = Grid(grid_file)
        ny, nx = g.header['dim_px']
        num_sweep = g.header['num_sweep_signal']

        for ch in g.header['channels']:
            assert ch in g.signals, f"Channel '{ch}' missing from signals"
            assert g.signals[ch].shape == (ny, nx, num_sweep), \
                f"Channel '{ch}' shape {g.signals[ch].shape} != expected ({ny}, {nx}, {num_sweep})"

    def test_params_shape_matches_header(self, grid_file):
        """Params array shape must match (ny, nx, num_parameters)."""
        g = Grid(grid_file)
        ny, nx = g.header['dim_px']
        num_param = g.header['num_parameters']
        assert g.signals['params'].shape == (ny, nx, num_param)

    def test_channel_count_matches_header(self, grid_file):
        """Number of channel entries must equal num_channels."""
        g = Grid(grid_file)
        assert len(g.header['channels']) == g.header['num_channels']

    def test_sweep_signal_monotonic(self, grid_file):
        """Sweep signal must be strictly monotonic."""
        g = Grid(grid_file)
        sweep = g.signals['sweep_signal']
        diffs = np.diff(sweep)
        # all positive or all negative
        assert np.all(diffs > 0) or np.all(diffs < 0), \
            "sweep_signal is not strictly monotonic"

    def test_sweep_signal_length(self, grid_file):
        """Sweep signal length must match num_sweep_signal."""
        g = Grid(grid_file)
        assert len(g.signals['sweep_signal']) == g.header['num_sweep_signal']

    def test_topo_shape(self, grid_file):
        """Topo must be 2D matching grid pixel dimensions."""
        g = Grid(grid_file)
        ny, nx = g.header['dim_px']
        assert g.signals['topo'].shape == (ny, nx)

    def test_no_unexpected_nans_in_signals(self, grid_file):
        """Signal arrays should not contain all-NaN slices."""
        g = Grid(grid_file)
        for ch in g.header['channels']:
            arr = g.signals[ch]
            # Each pixel should have at least some valid data
            assert not np.all(np.isnan(arr)), \
                f"Channel '{ch}' is entirely NaN"

    def test_required_header_keys(self, grid_file):
        """Header must contain all required keys."""
        g = Grid(grid_file)
        required = [
            'dim_px', 'num_sweep_signal', 'num_parameters',
            'channels', 'num_channels', 'sweep_signal'
        ]
        for key in required:
            assert key in g.header, f"Missing required header key: {key}"

    def test_signals_contains_all_expected_keys(self, grid_file):
        """Signals dict must have params, sweep_signal, topo, plus all channels."""
        g = Grid(grid_file)
        expected_keys = {'params', 'sweep_signal', 'topo'} | set(g.header['channels'])
        actual_keys = set(g.signals.keys())
        assert expected_keys == actual_keys, \
            f"Unexpected signals keys. Missing: {expected_keys - actual_keys}, Extra: {actual_keys - expected_keys}"


class TestScanInvariants:
    """Invariants that must hold for any valid scan file."""

    def test_signal_shapes_match_header(self, scan_file):
        """Each channel forward/backward shape must match (ny, nx)."""
        s = Scan(scan_file)
        ny, nx = s.header['scan_pixels']

        for ch in s.signals:
            fwd = s.signals[ch]['forward']
            bwd = s.signals[ch]['backward']
            assert fwd.shape == (ny, nx), \
                f"Channel '{ch}' forward shape {fwd.shape} != ({ny}, {nx})"
            assert bwd.shape == (ny, nx), \
                f"Channel '{ch}' backward shape {bwd.shape} != ({ny}, {nx})"

    def test_both_directions_present(self, scan_file):
        """Every channel must have both forward and backward arrays."""
        s = Scan(scan_file)
        for ch in s.signals:
            assert 'forward' in s.signals[ch], f"'{ch}' missing 'forward'"
            assert 'backward' in s.signals[ch], f"'{ch}' missing 'backward'"

    def test_channel_count_matches_data_info(self, scan_file):
        """Number of signal channels must match data_info names."""
        s = Scan(scan_file)
        expected_channels = list(s.header['data_info']['Name'])
        actual_channels = list(s.signals.keys())
        assert actual_channels == expected_channels

    def test_no_unexpected_nans(self, scan_file):
        """No channel should be entirely NaN."""
        s = Scan(scan_file)
        for ch in s.signals:
            assert not np.all(np.isnan(s.signals[ch]['forward'])), \
                f"Channel '{ch}' forward is entirely NaN"

    def test_required_header_keys(self, scan_file):
        """Header must contain essential keys."""
        s = Scan(scan_file)
        required = ['scan_pixels', 'scan_range', 'scan_offset', 'data_info']
        for key in required:
            assert key in s.header, f"Missing required header key: {key}"


class TestSpecInvariants:
    """Invariants that must hold for any valid spec file."""

    def test_columns_consistent_length(self, spec_file):
        """All signal columns must have the same length."""
        sp = Spec(spec_file)
        lengths = [len(v) for v in sp.signals.values()]
        assert len(set(lengths)) == 1, \
            f"Column lengths are inconsistent: {lengths}"

    def test_has_at_least_one_column(self, spec_file):
        """Spec must have at least one data column."""
        sp = Spec(spec_file)
        assert len(sp.signals) >= 1

    def test_no_empty_columns(self, spec_file):
        """No column should have zero length."""
        sp = Spec(spec_file)
        for key, val in sp.signals.items():
            assert len(val) > 0, f"Column '{key}' is empty"

    def test_no_unexpected_nans(self, spec_file):
        """No column should be entirely NaN."""
        sp = Spec(spec_file)
        for key, val in sp.signals.items():
            assert not np.all(np.isnan(val)), f"Column '{key}' is entirely NaN"
