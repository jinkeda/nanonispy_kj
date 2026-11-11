"""
Tests for the .sxm, .dat and .3ds writers.

Covers byte-identical rewrites of the real example files, modify-then-
write round trips, files created from scratch, the mixed-direction
reader fix, and error handling.
"""

import os

import numpy as np
import numpy.testing as npt
import pytest

from nanonispy2 import Grid, Scan, Spec, write_3ds, write_dat, write_sxm
from nanonispy2.core.exceptions import UnhandledFileError
from nanonispy2.parsers.header import parse_spec_header
from nanonispy2.writers.numfmt import format_eng, format_sci
from nanonispy2.writers.sxm import render_header_blocks, split_header_blocks

RNG = np.random.default_rng(12345)


def _read(path):
    with open(path, 'rb') as fh:
        return fh.read()


def _frames_expected(channels):
    return sum(2 if d == 'both' else 1 for _, _, d in channels)


def _make_signals(channels, nx, ny, nan_from_line=None):
    """Random float32-representable data for each recorded direction."""
    dirs = {'both': ('forward', 'backward'), 'forward': ('forward',),
            'backward': ('backward',)}
    signals = {}
    for name, _, direction in channels:
        signals[name] = {}
        for d in dirs[direction]:
            arr = RNG.normal(size=(ny, nx)).astype(np.float32) * np.float32(1e-9)
            if nan_from_line is not None:
                arr[nan_from_line:, :] = np.nan
            signals[name][d] = arr
    return signals


def _assert_signals_equal(read_back, given):
    assert list(read_back) == list(given)
    for ch in given:
        assert set(read_back[ch]) == set(given[ch]), ch
        for d in given[ch]:
            npt.assert_array_equal(read_back[ch][d],
                                   np.asarray(given[ch][d], dtype=np.float32),
                                   err_msg=f"{ch}/{d}")


# ------------------------------------------------------------ number format

class TestNumberFormat:

    def test_reproduces_every_real_dat_number(self, spec_files):
        """8-digit engineering style reproduces all tokens of the real files."""
        count = 0
        for path in spec_files:
            lines = _read(path).decode('ascii').split('\r\n')
            start = lines.index('[DATA]') + 2
            for line in lines[start:]:
                for token in filter(None, line.split('\t')):
                    assert format_eng(float(token), 8) == token
                    count += 1
        assert count > 1000

    def test_sci_matches_sxm_style(self):
        assert format_sci(5e-9, 6) == '5.000000E-9'
        assert format_sci(90, 3) == '9.000E+1'
        assert format_sci(-1.135e-11, 3) == '-1.135E-11'

    def test_exact_fallback(self):
        assert float(format_sci(12.3456789, 3)) == 12.3456789
        assert float(format_eng(1 / 3, None)) == 1 / 3

    def test_special_values(self):
        assert format_eng(float('nan')) == 'NaN'
        assert format_eng(float('inf')) == 'Inf'
        assert format_eng(0.0) == '0.0000000E+0'


# ----------------------------------------------------------- .sxm rewrites

class TestScanRewrite:

    def test_byte_identical(self, scan_files, tmp_path):
        """Criterion 1: Scan(f).write(out) reproduces every real file."""
        for path in scan_files:
            out = tmp_path / os.path.basename(path)
            Scan(path).write(str(out))
            assert _read(out) == _read(path), os.path.basename(path)

    def test_header_blocks_round_trip(self, scan_files):
        for path in scan_files:
            raw = _read(path)
            text = raw[:raw.index(b':SCANIT_END:')].decode()
            assert render_header_blocks(split_header_blocks(text)) == text

    def test_modify_then_write(self, scan_file, tmp_path):
        """Criterion 3: a changed channel comes back exactly (float32)."""
        scan = Scan(scan_file)
        signals = {ch: dict(d) for ch, d in scan.signals.items()}
        new_z = RNG.normal(size=signals['Z']['forward'].shape)
        signals['Z']['forward'] = new_z
        out = tmp_path / 'modified.sxm'
        scan.write(str(out), signals=signals)

        back = Scan(str(out))
        npt.assert_array_equal(back.signals['Z']['forward'], new_z.astype(np.float32))
        npt.assert_array_equal(back.signals['Z']['backward'], scan.signals['Z']['backward'])
        npt.assert_array_equal(back.signals['Current']['forward'],
                               scan.signals['Current']['forward'])
        assert os.path.getsize(out) == os.path.getsize(scan_file)

    def test_rebuild_real_file_from_builtin_template(self, scan_file, tmp_path):
        """write_sxm with FGT_0020's values reproduces it byte for byte."""
        raw = _read(scan_file)
        lines = raw.split(b'\n')
        scan = Scan(scan_file)
        out = tmp_path / 'FGT_0020.sxm'
        write_sxm(
            str(out), scan.signals,
            scan_range=(5e-9, 5e-9), scan_offset=(1.380225e-7, 4.141911e-7),
            scan_angle=90, scan_dir='down', bias=0.01, setpoint=5e-11,
            rec_date='02.12.2025', rec_time='22:11:05', acq_time=854.8, comment='',
            channels=[('Z', 'm', 'both', 30, 1.8e-8, 0),
                      ('Current', 'A', 'both', 0, 1e-9, -1.135e-11),
                      ('LI_Demod_1_X', 'A', 'both', 86, 1e-9, 0),
                      ('LI_Demod_1_Y', 'A', 'both', 87, 1e-9, 0)],
            extra_header={
                'SCAN_FILE': lines[15].decode(),
                'NanonisMain>Session Path': lines[34].decode(),
                'Scan>channels': 'Current (A);Z (m);LI Demod 1 X (A);LI Demod 1 Y (A)',
            })
        assert _read(out) == raw


# ------------------------------------------------------- .sxm from scratch

SCRATCH_CASES = [
    pytest.param(dict(scan_dir=d, scan_angle=a), id=f'{d}-angle{a}')
    for d in ('up', 'down') for a in (0, 90, 30, -45)
]


class TestScanFromScratch:

    def _write_and_check(self, tmp_path, channels, nx, ny, name='s.sxm',
                         nan_from_line=None, **kwargs):
        params = dict(scan_range=(12e-9, 7.5e-9), scan_offset=(-1.25e-7, 3.5e-8),
                      scan_angle=0.0, scan_dir='down', bias=-0.35,
                      setpoint=1.2e-10)
        params.update(kwargs)
        signals = _make_signals(channels, nx, ny, nan_from_line)
        out = tmp_path / name
        write_sxm(str(out), signals, channels=channels, **params)

        raw = _read(out)
        data_start = raw.index(b':SCANIT_END:') + len(b':SCANIT_END:\n\n\n') + 2
        assert raw[data_start - 2:data_start] == b'\x1a\x04'
        assert len(raw) == data_start + _frames_expected(channels) * nx * ny * 4

        scan = Scan(str(out))
        h = scan.header
        npt.assert_array_equal(h['scan_pixels'], [nx, ny])
        npt.assert_array_equal(h['scan_range'], params['scan_range'])
        npt.assert_array_equal(h['scan_offset'], params['scan_offset'])
        assert float(h['scan_angle']) == params['scan_angle']
        assert h['scan_dir'] == params['scan_dir']
        assert h['bias'] == params['bias']
        assert float(h['z-controller']['Setpoint'][0].split()[0]) == params['setpoint']
        assert list(h['data_info']['Name']) == [c[0] for c in channels]
        assert list(h['data_info']['Unit']) == [c[1] for c in channels]
        assert list(h['data_info']['Direction']) == [c[2] for c in channels]
        assert h['scanit_type'].split() == ['FLOAT', 'MSBFIRST']
        _assert_signals_equal(scan.signals, signals)
        return out, signals, scan

    @pytest.mark.parametrize('kwargs', SCRATCH_CASES)
    def test_dir_and_angle(self, tmp_path, kwargs):
        channels = [('Z', 'm', 'both'), ('Current', 'A', 'both')]
        self._write_and_check(tmp_path, channels, 32, 32, **kwargs)

    @pytest.mark.parametrize('nx,ny', [(37, 23), (23, 37), (64, 16), (1, 5)])
    def test_non_square_and_odd(self, tmp_path, nx, ny):
        channels = [('Z', 'm', 'both')]
        self._write_and_check(tmp_path, channels, nx, ny, scan_angle=30.0)

    def test_mixed_directions(self, tmp_path):
        """Mixed both/forward/backward channels (reader bug fix)."""
        channels = [('Z', 'm', 'both'), ('Current', 'A', 'forward'),
                    ('Phase', 'deg', 'backward'), ('Amplitude', 'm', 'both')]
        out, signals, scan = self._write_and_check(tmp_path, channels, 37, 23)
        assert set(scan.signals['Current']) == {'forward'}
        assert set(scan.signals['Phase']) == {'backward'}

        # raw file order: DATA_INFO order, forward before backward, no flips
        raw = _read(out)
        start = raw.index(b':SCANIT_END:') + 17
        data = np.frombuffer(raw[start:], dtype='>f4').reshape(-1, 23, 37)
        expected = [signals['Z']['forward'], signals['Z']['backward'],
                    signals['Current']['forward'], signals['Phase']['backward'],
                    signals['Amplitude']['forward'], signals['Amplitude']['backward']]
        for frame, exp in zip(data, expected):
            npt.assert_array_equal(frame, exp)

    def test_only_single_direction_channels(self, tmp_path):
        channels = [('Z', 'm', 'forward'), ('Current', 'A', 'forward')]
        self._write_and_check(tmp_path, channels, 20, 10)

    def test_aborted_scan_nan_lines(self, tmp_path):
        channels = [('Z', 'm', 'both'), ('Current', 'A', 'forward')]
        _, _, scan = self._write_and_check(tmp_path, channels, 30, 40, nan_from_line=17)
        z = scan.signals['Z']['forward']
        assert np.isnan(z[17:]).all() and np.isfinite(z[:17]).all()

    def test_nanonis_version_1(self, tmp_path):
        """Version 1 stores SCAN_PIXELS as 'ny nx'; read back as (nx, ny)."""
        channels = [('Z', 'm', 'both'), ('Current', 'A', 'forward')]
        out, _, scan = self._write_and_check(tmp_path, channels, 37, 23, nanonis_version=1)
        lines = _read(out).decode('latin-1').split('\n')
        assert lines[1] == '1'
        pix = lines[lines.index(':SCAN_PIXELS:') + 1].split()
        assert pix == ['23', '37']
        assert scan.signals['Z']['forward'].shape == (23, 37)

    def test_metadata_fields(self, tmp_path):
        out = tmp_path / 'meta_0007.sxm'
        z = np.zeros((4, 6))
        write_sxm(str(out), {'Z': {'forward': z}}, channels=[('Z', 'm', 'forward')],
                  scan_range=(1e-8, 1e-8), rec_date='24.12.2025', rec_time='08:30:15',
                  acq_time=123.4, comment='line one\nline two',
                  extra_header={'Scan>series name': 'synthetic_', 'REC_TEMP': '4.300'})
        h = Scan(str(out)).header
        assert h['rec_date'] == '24.12.2025'
        assert h['rec_time'] == '08:30:15'
        assert h['acq_time'] == 123.4
        assert h['comment'] == 'line one\nline two'
        assert h['scan>series name'] == 'synthetic_'
        assert h['rec_temp'] == '4.300'
        assert h['scan_file'] == os.path.abspath(str(out))
        assert h['scan>pixels/line'] == '6' and h['scan>lines'] == '4'

    def test_inexact_values_round_trip(self, tmp_path):
        """Values not representable in Nanonis' digit counts still read back exactly."""
        out = tmp_path / 'exact.sxm'
        rng, off, ang, bias = (1.234567891e-9, 9.87654321e-9), (1.1e-7, -2.2222222e-7), 12.3456, 0.0123456789
        write_sxm(str(out), {'Z': {'forward': np.zeros((3, 3))}},
                  channels=[('Z', 'm', 'forward')], scan_range=rng, scan_offset=off,
                  scan_angle=ang, bias=bias, setpoint=(3.3333e-3, 'V'))
        h = Scan(str(out)).header
        npt.assert_array_equal(h['scan_range'], rng)
        npt.assert_array_equal(h['scan_offset'], off)
        assert float(h['scan_angle']) == ang and h['bias'] == bias
        assert h['z-controller']['Setpoint'][0] == '3.3333E-3 V'

    def test_template_keeps_other_entries(self, scan_file, tmp_path):
        out = tmp_path / 'from_template.sxm'
        tpl = Scan(scan_file)
        signals = {k: dict(v) for k, v in tpl.signals.items()}
        write_sxm(str(out), signals, template=scan_file, bias=-1.5, scan_dir='up')
        new = Scan(str(out))
        assert new.header['bias'] == -1.5
        assert new.header['scan_dir'] == 'up'
        assert new.header['bias>bias (v)'] == '-1.5E+0'
        for key in ('piezo configuration>calib. x (m/v)', 'lock-in>frequency (hz)',
                    'scan_range', 'rec_date', 'acq_time'):
            v_old, v_new = tpl.header[key], new.header[key]
            npt.assert_array_equal(np.asarray(v_new), np.asarray(v_old), err_msg=key)
        assert new.header['data_info'] == tpl.header['data_info']
        _assert_signals_equal(new.signals, signals)


# ------------------------------------------------------------- .sxm errors

class TestScanWriteErrors:

    def _ok(self):
        return dict(channels=[('Z', 'm', 'both')], scan_range=(1e-8, 1e-8))

    def _sig(self, nx=4, ny=3):
        return {'Z': {'forward': np.zeros((ny, nx)), 'backward': np.zeros((ny, nx))}}

    def test_wrong_extension(self, tmp_path, scan_file):
        with pytest.raises(UnhandledFileError):
            write_sxm(str(tmp_path / 'a.dat'), self._sig(), **self._ok())
        with pytest.raises(UnhandledFileError):
            Scan(scan_file).write(str(tmp_path / 'a.3ds'))

    def test_existing_file(self, tmp_path, scan_file):
        out = tmp_path / 'a.sxm'
        out.write_bytes(b'keep me')
        with pytest.raises(FileExistsError):
            write_sxm(str(out), self._sig(), **self._ok())
        with pytest.raises(FileExistsError):
            Scan(scan_file).write(str(out))
        assert out.read_bytes() == b'keep me'
        Scan(scan_file).write(str(out), overwrite=True)
        assert _read(out) == _read(scan_file)

    def test_shape_mismatch(self, tmp_path):
        sig = self._sig()
        sig['Z']['backward'] = np.zeros((4, 4))
        with pytest.raises(ValueError, match='shape'):
            write_sxm(str(tmp_path / 'a.sxm'), sig, **self._ok())
        with pytest.raises(ValueError, match='shape'):
            write_sxm(str(tmp_path / 'b.sxm'), self._sig(), pixels=(5, 3), **self._ok())

    def test_direction_mismatch(self, tmp_path):
        sig = {'Z': {'forward': np.zeros((3, 4))}}
        with pytest.raises(ValueError, match='recorded'):
            write_sxm(str(tmp_path / 'a.sxm'), sig, **self._ok())
        sig = self._sig()
        with pytest.raises(ValueError, match='recorded'):
            write_sxm(str(tmp_path / 'b.sxm'), sig, channels=[('Z', 'm', 'forward')],
                      scan_range=(1e-8, 1e-8))

    def test_channel_mismatch(self, tmp_path, scan_file):
        scan = Scan(scan_file)
        signals = dict(scan.signals)
        signals['Extra'] = signals['Z']
        with pytest.raises(ValueError, match='not in the header'):
            scan.write(str(tmp_path / 'a.sxm'), signals=signals)
        del signals['Extra'], signals['Z']
        with pytest.raises(ValueError, match="missing channel 'Z'"):
            scan.write(str(tmp_path / 'b.sxm'), signals=signals)
        assert not os.path.exists(tmp_path / 'a.sxm')

    def test_direction_case_insensitive(self, tmp_path):
        out = tmp_path / 'a.sxm'
        write_sxm(str(out), self._sig(), channels=[('Z', 'm', ' Both ')],
                  scan_range=(1e-8, 1e-8))
        assert Scan(str(out)).header['data_info']['Direction'] == ('both',)

    @pytest.mark.parametrize('bad', ['fwd', 'forward+backward', 'up', ''])
    def test_unknown_direction(self, tmp_path, bad):
        with pytest.raises(ValueError, match='unknown direction'):
            write_sxm(str(tmp_path / 'a.sxm'), self._sig(),
                      channels=[('Z', 'm', bad)], scan_range=(1e-8, 1e-8))

    def test_unknown_direction_in_header(self, tmp_path, scan_file):
        scan = Scan(scan_file)
        header = scan.header_raw.replace('\t30\tZ\tm\tboth', '\t30\tZ\tm\tsideways')
        with pytest.raises(ValueError, match='unknown direction'):
            scan.write(str(tmp_path / 'a.sxm'), header_raw=header)

    @pytest.mark.parametrize('rng', [(0, 1e-8), (-1e-8, 1e-8), (np.nan, 1e-8),
                                     (np.inf, 1e-8), (1e-8,), 'abc'])
    def test_bad_scan_range(self, tmp_path, rng):
        with pytest.raises(ValueError, match='scan_range'):
            write_sxm(str(tmp_path / 'a.sxm'), self._sig(),
                      channels=[('Z', 'm', 'both')], scan_range=rng)

    def test_bad_scalar_arguments(self, tmp_path):
        out = str(tmp_path / 'a.sxm')
        for kwargs, msg in [(dict(scan_dir='left'), 'scan_dir'),
                            (dict(scan_angle=np.nan), 'scan_angle'),
                            (dict(bias=np.inf), 'bias'),
                            (dict(rec_date='2025-12-02'), 'rec_date'),
                            (dict(comment=':EVIL:'), 'comment'),
                            (dict(extra_header={'BIAS': 1.0}), 'BIAS'),
                            (dict(nanonis_version=0), 'nanonis_version')]:
            with pytest.raises(ValueError, match=msg):
                write_sxm(out, self._sig(), **self._ok(), **kwargs)

    def test_little_endian_header_rejected(self, tmp_path, scan_file):
        scan = Scan(scan_file)
        header = scan.header_raw.replace('MSBFIRST', 'LSBFIRST')
        with pytest.raises(ValueError, match='MSBFIRST'):
            scan.write(str(tmp_path / 'a.sxm'), header_raw=header)

    def test_mixed_file_read_correctly(self, scan_file, tmp_path):
        """A real header switched to mixed directions reads the right frames."""
        scan = Scan(scan_file)
        header = scan.header_raw.replace('\tCurrent\tA\tboth', '\tCurrent\tA\tforward')
        signals = {k: dict(v) for k, v in scan.signals.items()}
        del signals['Current']['backward']
        out = tmp_path / 'mixed.sxm'
        scan.write(str(out), signals=signals, header_raw=header)
        back = Scan(str(out))
        assert set(back.signals['Current']) == {'forward'}
        # one frame fewer; header is 3 bytes longer ('forward' vs 'both')
        assert os.path.getsize(out) == os.path.getsize(scan_file) - 256 * 256 * 4 + 3
        _assert_signals_equal(back.signals, signals)


# ------------------------------------------------------------------- .dat

class TestSpecWrite:

    def test_rewrite_identical(self, spec_files, tmp_path):
        """Criterion 2: same header and signals on re-read, and same bytes."""
        for path in spec_files:
            spec = Spec(path)
            out = tmp_path / os.path.basename(path)
            spec.write(str(out))
            back = Spec(str(out))
            assert back.header == spec.header
            assert list(back.signals) == list(spec.signals)
            for k in spec.signals:
                npt.assert_array_equal(back.signals[k], spec.signals[k])
            assert _read(out) == _read(path)

    def test_modified_header_rerendered(self, spec_file, tmp_path):
        spec = Spec(spec_file)
        spec.header['User'] = 'tester'
        out = tmp_path / 'a.dat'
        spec.write(str(out))
        back = Spec(str(out))
        assert back.header == spec.header
        # unchanged lines are byte-identical
        assert _read(out).replace(b'User\ttester\t', b'User\t\t') == _read(spec_file)

    def test_modify_then_write(self, spec_file, tmp_path):
        """Criterion 3: precision 8 within 5e-8 relative, None exact."""
        spec = Spec(spec_file)
        signals = dict(spec.signals)
        new = RNG.normal(size=len(signals['Current (A)'])) * 1e-9
        new[5] = np.nan
        signals['Current (A)'] = new

        spec.write(str(tmp_path / 'p8.dat'), signals=signals)
        got = Spec(str(tmp_path / 'p8.dat')).signals['Current (A)']
        npt.assert_allclose(got, new, rtol=5e-8, atol=0, equal_nan=True)

        spec.write(str(tmp_path / 'exact.dat'), signals=signals, precision=None)
        got = Spec(str(tmp_path / 'exact.dat')).signals['Current (A)']
        npt.assert_array_equal(got, new)

    def test_from_scratch(self, tmp_path):
        """Criterion 5."""
        v = np.linspace(-0.1, 0.1, 101)
        signals = {'Bias calc (V)': v, 'Current (A)': 1e-9 * np.tanh(10 * v),
                   'Current (A) [filt]': np.full(101, np.nan)}
        header = {'Saved Date': '01.01.2026 12:00:00', 'User': '', 'X (m)': 1.5e-9,
                  'Z-Ctrl hold': True, 'Bias Spectroscopy>Num Pixel': 101,
                  'Bias Spectroscopy>Channels': ['Current (A)', 'Bias (V)']}
        out = tmp_path / 'scratch.dat'
        write_dat(str(out), signals, header, precision=None)

        raw = _read(out)
        assert raw.startswith(b'Experiment\tbias spectroscopy\t\r\n')
        assert b'\n' not in raw.replace(b'\r\n', b'')
        back = Spec(str(out))
        assert back.header == {
            'Experiment': 'bias spectroscopy', 'Saved Date': '01.01.2026 12:00:00',
            'User': '', 'X (m)': '1.5E-9', 'Z-Ctrl hold': 'TRUE',
            'Bias Spectroscopy>Num Pixel': '101',
            'Bias Spectroscopy>Channels': 'Current (A);Bias (V)'}
        assert list(back.signals) == list(signals)
        for k in signals:
            npt.assert_array_equal(back.signals[k], signals[k])

    def test_header_parses_like_real(self, spec_file, tmp_path):
        """A real header dict re-rendered by write_dat parses identically."""
        spec = Spec(spec_file)
        out = tmp_path / 'b.dat'
        write_dat(str(out), spec.signals, spec.header)
        assert _read(out) == _read(spec_file)
        assert parse_spec_header(Spec(str(out)).header_raw) == spec.header

    def test_errors(self, tmp_path, spec_file):
        sig = {'A (V)': np.zeros(3)}
        with pytest.raises(UnhandledFileError):
            write_dat(str(tmp_path / 'a.sxm'), sig)
        with pytest.raises(UnhandledFileError):
            Spec(spec_file).write(str(tmp_path / 'a.txt'))
        (tmp_path / 'e.dat').write_text('x')
        with pytest.raises(FileExistsError):
            write_dat(str(tmp_path / 'e.dat'), sig)
        with pytest.raises(FileExistsError):
            Spec(spec_file).write(str(tmp_path / 'e.dat'))
        with pytest.raises(ValueError, match='different lengths'):
            write_dat(str(tmp_path / 'b.dat'), {'A': np.zeros(3), 'B': np.zeros(4)})
        with pytest.raises(ValueError, match='1-D'):
            write_dat(str(tmp_path / 'b.dat'), {'A': np.zeros((3, 2))})
        with pytest.raises(ValueError, match='tabs'):
            write_dat(str(tmp_path / 'b.dat'), {'A\tB': np.zeros(3)})
        with pytest.raises(ValueError, match='line breaks'):
            write_dat(str(tmp_path / 'b.dat'), sig, {'Comment': 'a\r\nb'})
        assert not os.path.exists(tmp_path / 'b.dat')


# ------------------------------------------------------------------- .3ds

class TestGridWrite:

    def test_from_scratch_round_trip(self, tmp_path):
        ny, nx, npts = 5, 7, 11
        signals = {'Current (A)': RNG.normal(size=(ny, nx, npts)).astype(np.float32),
                   'LI Demod 1 X (A)': RNG.normal(size=(ny, nx, npts)).astype(np.float32)}
        z = RNG.normal(size=(ny, nx)).astype(np.float32)
        out = tmp_path / 'g.3ds'
        write_3ds(str(out), signals, sweep_start=0.1, sweep_end=-0.1,
                  grid_center=(1e-7, -2e-7), grid_size=(7e-9, 5e-9), grid_angle=-45,
                  experiment_parameters={'X (m)': np.zeros((ny, nx)), 'Z (m)': z},
                  start_time='01.01.2026 10:00:00', comment='synthetic')
        g = Grid(str(out))
        assert g.header['dim_px'] == [nx, ny]
        assert g.header['pos_xy'] == [1e-7, -2e-7]
        assert g.header['size_xy'] == [7e-9, 5e-9]
        assert g.header['angle'] == -45
        assert g.header['channels'] == list(signals)
        assert g.header['num_sweep_signal'] == npts
        assert g.header['experimental_parameters'] == ['X (m)', 'Z (m)']
        assert g.header['comment'] == 'synthetic'
        for k in signals:
            npt.assert_array_equal(g.signals[k], signals[k])
        npt.assert_array_equal(g.signals['topo'], z)
        # Grid rebuilds the sweep from the float32-stored endpoints
        npt.assert_array_equal(
            g.signals['sweep_signal'],
            np.linspace(np.float32(0.1), np.float32(-0.1), npts, dtype=np.float32))
        nparam = 4
        assert os.path.getsize(out) == len(_read(out).split(b':HEADER_END:\r\n')[0]) \
            + len(b':HEADER_END:\r\n') + ny * nx * (nparam + 2 * npts) * 4

    def test_single_channel_default_params(self, tmp_path):
        out = tmp_path / 'g.3ds'
        write_3ds(str(out), {'Current (A)': np.ones((2, 3, 4))}, sweep_start=-1,
                  sweep_end=1, grid_size=(1e-9, 1e-9))
        g = Grid(str(out))
        assert g.header['channels'] == ['Current (A)']
        assert g.signals['topo'].shape == (2, 3)

    def test_rewrite_real_grid(self, grid_file, tmp_path):
        out = tmp_path / 'g.3ds'
        Grid(grid_file).write(str(out))
        assert _read(out) == _read(grid_file)

    def test_errors(self, tmp_path):
        ok = dict(sweep_start=0, sweep_end=1, grid_size=(1e-9, 1e-9))
        with pytest.raises(UnhandledFileError):
            write_3ds(str(tmp_path / 'g.sxm'), {'I': np.zeros((2, 2, 3))}, **ok)
        with pytest.raises(ValueError, match='one shape'):
            write_3ds(str(tmp_path / 'g.3ds'),
                      {'I': np.zeros((2, 2, 3)), 'J': np.zeros((2, 2, 4))}, **ok)
        with pytest.raises(ValueError, match='positive'):
            write_3ds(str(tmp_path / 'g.3ds'), {'I': np.zeros((2, 2, 3))},
                      sweep_start=0, sweep_end=1, grid_size=(0, 1e-9))
