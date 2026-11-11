"""
Typed header definitions for Nanonis file types.

Provides TypedDict classes for autocompletion and type checking of parsed headers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Union

from typing_extensions import TypedDict

import numpy as np


class GridHeader(TypedDict, total=False):
    """Parsed header from a Nanonis .3ds grid file."""

    dim_px: List[int]
    pos_xy: List[float]
    size_xy: List[float]
    angle: float
    sweep_signal: str
    fixed_parameters: Union[str, List[str]]
    experimental_parameters: Union[str, List[str]]
    num_parameters: int
    experiment_size: int
    num_sweep_signal: int
    channels: List[str]
    num_channels: int
    measure_delay: float
    experiment_name: str
    start_time: str
    end_time: str
    user: str
    comment: str


# Functional syntax because the reader's keys include hyphens
# ('z-controller', 'multipass-config'), which class syntax cannot express.
# Keys are the lower-cased tag names; other ':Section>Key:' entries appear
# as lower-cased string values, e.g. 'bias>bias (v)'.
ScanHeader = TypedDict('ScanHeader', {
    'nanonis_version': str,
    'scanit_type': str,
    'rec_date': str,
    'rec_time': str,
    'rec_temp': str,
    'scan_file': str,
    'scan_pixels': np.ndarray,     # [nx, ny], also for NANONIS_VERSION < 2
    'scan_range': np.ndarray,
    'scan_offset': np.ndarray,
    'scan_time': np.ndarray,
    'scan_angle': str,
    'scan_dir': str,
    'bias': np.float64,
    'acq_time': np.float64,
    'data_info': Dict[str, Any],
    'z-controller': Dict[str, Any],
    'multipass-config': Dict[str, Any],
    'comment': str,
}, total=False)
ScanHeader.__doc__ = "Parsed header from a Nanonis .sxm scan file."


class SpecHeader(TypedDict, total=False):
    """Parsed header from a Nanonis .dat spec file."""

    # Spec headers are key-value pairs; keys vary by experiment.
    # Common keys include:
    Experiment: str
    Date: str
    User: str
    X: str
    Y: str
    Z: str
