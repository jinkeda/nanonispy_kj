"""
Pytest fixtures and configuration for nanonispy2 tests.
"""

import os
import pytest

# Base path for test data files
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'nano_spec', 'data')


@pytest.fixture
def grid_file():
    """Path to a real Nanonis grid (.3ds) file."""
    path = os.path.join(DATA_DIR, 'Grid Spectroscopy017.3ds')
    if not os.path.exists(path):
        pytest.skip(f"Test data not found: {path}")
    return path


@pytest.fixture
def scan_file():
    """Path to a real Nanonis scan (.sxm) file."""
    path = os.path.join(DATA_DIR, 'FGT_0020.sxm')
    if not os.path.exists(path):
        pytest.skip(f"Test data not found: {path}")
    return path


@pytest.fixture
def scan_files():
    """Paths to all available Nanonis scan (.sxm) files."""
    names = ['FGT_0020.sxm', 'FGT_0021.sxm', 'FGT_0022.sxm']
    paths = [os.path.join(DATA_DIR, n) for n in names]
    available = [p for p in paths if os.path.exists(p)]
    if not available:
        pytest.skip("No scan test data found")
    return available


@pytest.fixture
def spec_file():
    """Path to a real Nanonis spec (.dat) file."""
    path = os.path.join(DATA_DIR, 'Bias-Spectroscopy_00541.dat')
    if not os.path.exists(path):
        pytest.skip(f"Test data not found: {path}")
    return path


@pytest.fixture
def spec_files():
    """Paths to all available Nanonis spec (.dat) files."""
    names = ['Bias-Spectroscopy_00541.dat', 'Bias-Spectroscopy_00542.dat']
    paths = [os.path.join(DATA_DIR, n) for n in names]
    available = [p for p in paths if os.path.exists(p)]
    if not available:
        pytest.skip("No spec test data found")
    return available
