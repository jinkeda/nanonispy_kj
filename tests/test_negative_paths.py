"""
Negative-path tests for nanonispy2.

These tests verify that the library handles corrupted, truncated,
and invalid files gracefully with clear error messages.
"""

import os
import numpy as np
import pytest

from nanonispy2.read import Grid, Scan, Spec, UnhandledFileError


class TestInvalidExtension:
    """Verify rejection of unsupported file extensions."""

    def test_grid_rejects_sxm(self, tmp_path):
        """Grid raises for non-.3ds files."""
        f = tmp_path / "test.sxm"
        f.write_bytes(b"dummy data")
        with pytest.raises(UnhandledFileError):
            Grid(str(f))

    def test_scan_rejects_3ds(self, tmp_path):
        """Scan raises for non-.sxm files."""
        f = tmp_path / "test.3ds"
        f.write_bytes(b"dummy data")
        with pytest.raises(UnhandledFileError):
            Scan(str(f))

    def test_spec_rejects_sxm(self, tmp_path):
        """Spec raises for non-.dat files."""
        f = tmp_path / "test.sxm"
        f.write_bytes(b"dummy data")
        with pytest.raises(UnhandledFileError):
            Spec(str(f))

    def test_unknown_extension(self, tmp_path):
        """All classes reject unknown extensions."""
        f = tmp_path / "test.xyz"
        f.write_text("dummy")
        with pytest.raises(UnhandledFileError):
            Grid(str(f))
        with pytest.raises(UnhandledFileError):
            Scan(str(f))
        with pytest.raises(UnhandledFileError):
            Spec(str(f))


class TestEmptyFile:
    """Verify behavior with empty (0-byte) files."""

    def test_empty_3ds(self, tmp_path):
        """Empty .3ds file should raise an error."""
        f = tmp_path / "empty.3ds"
        f.write_bytes(b"")
        with pytest.raises(Exception):
            Grid(str(f))

    def test_empty_sxm(self, tmp_path):
        """Empty .sxm file should raise an error."""
        f = tmp_path / "empty.sxm"
        f.write_bytes(b"")
        with pytest.raises(Exception):
            Scan(str(f))

    def test_empty_dat(self, tmp_path):
        """Empty .dat file should raise an error."""
        f = tmp_path / "empty.dat"
        f.write_bytes(b"")
        with pytest.raises(Exception):
            Spec(str(f))


class TestCorruptedHeader:
    """Verify behavior when header end tag is missing."""

    def test_missing_header_end_3ds(self, tmp_path):
        """3ds with no :HEADER_END: should raise an error."""
        f = tmp_path / "corrupt.3ds"
        f.write_text("some header data without end tag")
        with pytest.raises(Exception):
            Grid(str(f))

    def test_missing_header_end_sxm(self, tmp_path):
        """sxm with no SCANIT_END should raise an error."""
        f = tmp_path / "corrupt.sxm"
        f.write_text("some header data without end tag")
        with pytest.raises(Exception):
            Scan(str(f))


class TestTruncatedData:
    """Verify behavior when file data section is truncated."""

    def test_truncated_3ds(self, grid_file, tmp_path):
        """3ds file with truncated data produces mostly-zero arrays."""
        # Read valid file, keep header but truncate most of the data
        with open(grid_file, 'rb') as f:
            content = f.read()

        # Find header end tag and keep only a small portion after it
        header_end = content.find(b':HEADER_END:')
        assert header_end > 0, "Test data doesn't contain header end tag"
        truncated = content[:header_end + len(b':HEADER_END:\r\n') + 16]

        truncated_file = tmp_path / "truncated.3ds"
        truncated_file.write_bytes(truncated)

        # NumPy silently truncates; data will be mostly zeros
        g = Grid(str(truncated_file))
        for ch in g.header['channels']:
            zero_frac = np.mean(g.signals[ch] == 0)
            assert zero_frac > 0.9, \
                f"Truncated file should produce mostly-zero data for '{ch}'"

    def test_truncated_sxm(self, scan_file, tmp_path):
        """sxm file with partial data should raise or handle gracefully."""
        with open(scan_file, 'rb') as f:
            content = f.read()

        # Find header end tag and keep only a small portion after it
        header_end = content.find(b'SCANIT_END')
        assert header_end > 0
        truncated = content[:header_end + len(b'SCANIT_END\r\n') + 16]

        truncated_file = tmp_path / "truncated.sxm"
        truncated_file.write_bytes(truncated)

        with pytest.raises(Exception):
            Scan(str(truncated_file))


class TestTopoResolver:
    """Tests for the topo column resolver."""

    def test_finds_z_m(self):
        """Should find 'Z (m)' as first Z match."""
        from nanonispy2.read import _resolve_topo_index
        params = ['Sweep Start', 'Sweep End', 'X (m)', 'Y (m)', 'Z (m)']
        assert _resolve_topo_index(params) == 4

    def test_finds_z_nm(self):
        """Should find 'Z (nm)' variant."""
        from nanonispy2.read import _resolve_topo_index
        params = ['X (m)', 'Y (m)', 'Z (nm)', 'Current']
        assert _resolve_topo_index(params) == 2

    def test_finds_z_bracket(self):
        """Should find 'Z [m]' bracket variant."""
        from nanonispy2.read import _resolve_topo_index
        params = ['X [m]', 'Y [m]', 'Z [m]']
        assert _resolve_topo_index(params) == 2

    def test_finds_bare_z(self):
        """Should find bare 'Z' label."""
        from nanonispy2.read import _resolve_topo_index
        params = ['X', 'Y', 'Z']
        assert _resolve_topo_index(params) == 2

    def test_case_insensitive(self):
        """Should find 'z (m)' lowercase."""
        from nanonispy2.read import _resolve_topo_index
        params = ['x (m)', 'y (m)', 'z (m)']
        assert _resolve_topo_index(params) == 2

    def test_fallback_with_warning(self):
        """Should warn and return 4 when Z column not found."""
        from nanonispy2.read import _resolve_topo_index
        params = ['A', 'B', 'C', 'D', 'E']
        with pytest.warns(UserWarning, match="Z column not found"):
            idx = _resolve_topo_index(params)
        assert idx == 4
