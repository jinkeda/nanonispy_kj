"""
Number formatting in the styles Nanonis software writes.

Nanonis uses three distinct styles, all with a minimal exponent
(``E-9``, ``E+0`` rather than ``e-09``):

- **Scientific, fixed decimals** — fixed .sxm header tags, e.g.
  ``5.000000E-9`` (SCAN_RANGE), ``9.000E+1`` (SCAN_ANGLE).
- **Engineering, fixed significant digits** — .dat data columns, e.g.
  ``9.9999998E-3``, ``-146.39633E-9``, ``191.22446E-3`` (8 digits,
  exponent a multiple of 3, trailing zeros kept).
- **Engineering, trailing zeros stripped** — ``Section>Key`` header
  values, e.g. ``10E-3``, ``895E-6``, ``-146.225E-9``, ``0E+0``.

Every formatter can fall back to the shortest representation that
round-trips the float64 value exactly, so that header values written by
nanonispy2 come back exactly as given.
"""

import math
from decimal import Decimal
from typing import Optional, Tuple


def _special(value: float) -> Optional[str]:
    """Return the Nanonis spelling of NaN/Inf, or None for finite values."""
    if math.isnan(value):
        return 'NaN'
    if math.isinf(value):
        return 'Inf' if value > 0 else '-Inf'
    return None


def _digits_rounded(value: float, sig: int) -> Tuple[str, str, int]:
    """
    Round *value* to *sig* significant digits.

    Returns
    -------
    tuple
        (sign, digit string of length *sig*, decimal exponent of the
        first digit).
    """
    mantissa, exp = ('%.*e' % (sig - 1, value)).split('e')
    sign = '-' if mantissa.startswith('-') else ''
    digits = mantissa.lstrip('-').replace('.', '')
    return sign, digits, int(exp)


def _digits_shortest(value: float) -> Tuple[str, str, int]:
    """
    Shortest digit string that round-trips *value* as a float64.

    Returns
    -------
    tuple
        (sign, digit string without trailing zeros, decimal exponent of
        the first digit).
    """
    sign = '-' if math.copysign(1.0, value) < 0 else ''
    if value == 0:
        return sign, '0', 0
    tup = Decimal(repr(abs(float(value)))).normalize().as_tuple()
    digits = ''.join(str(d) for d in tup.digits)
    return sign, digits, len(digits) - 1 + tup.exponent


def _assemble_eng(sign: str, digits: str, exp: int, strip: bool) -> str:
    """Place the decimal point for an engineering (multiple-of-3) exponent."""
    if set(digits) == {'0'}:
        exp = 0
    eng_exp = (exp // 3) * 3
    n_int = exp - eng_exp + 1
    if len(digits) < n_int:
        digits = digits + '0' * (n_int - len(digits))
    int_part, frac = digits[:n_int], digits[n_int:]
    if strip:
        frac = frac.rstrip('0')
    body = int_part + ('.' + frac if frac else '')
    return f'{sign}{body}E{eng_exp:+d}'


def format_eng(value: float, sig: Optional[int] = 8, strip: bool = False) -> str:
    """
    Format *value* in Nanonis engineering notation.

    Parameters
    ----------
    value : float
        Value to format.
    sig : int or None, optional
        Number of significant digits (default 8, the .dat data style).
        ``None`` uses the shortest digit string that round-trips the
        float64 value exactly.
    strip : bool, optional
        Strip trailing zeros of the mantissa (header style, e.g.
        ``10E-3``). Default False (.dat data style, ``-146.39200E-9``).

    Returns
    -------
    str
    """
    value = float(value)
    special = _special(value)
    if special is not None:
        return special
    if sig is None:
        sign, digits, exp = _digits_shortest(value)
    else:
        if sig < 1:
            raise ValueError(f"sig must be >= 1 or None, got {sig}")
        sign, digits, exp = _digits_rounded(value, sig)
    return _assemble_eng(sign, digits, exp, strip)


def format_eng_exact(value: float, sig: int = 6) -> str:
    """
    Header-style engineering value (``50E-12``), exact if *sig* is not.

    Uses *sig* significant digits with trailing zeros stripped, as
    Nanonis does for ``Section>Key`` header entries, and falls back to
    the shortest exact representation if that would lose precision.
    """
    text = format_eng(value, sig, strip=True)
    if _special(float(value)) is None and float(text) != float(value):
        text = format_eng(value, None, strip=True)
    return text


def format_sci(value: float, decimals: int) -> str:
    """
    Scientific notation with fixed decimals and minimal exponent.

    Falls back to more decimals if *decimals* would not represent the
    float64 value exactly (e.g. ``format_sci(12.3456, 3)`` gives
    ``1.23456E+1`` rather than ``1.235E+1``).

    Examples
    --------
    >>> format_sci(5e-9, 6)
    '5.000000E-9'
    >>> format_sci(90, 3)
    '9.000E+1'
    """
    value = float(value)
    special = _special(value)
    if special is not None:
        return special
    mantissa, exp = ('%.*e' % (decimals, value)).split('e')
    text = f'{mantissa}E{int(exp):+d}'
    if float(text) != value:
        sign, digits, exp_ = _digits_shortest(value)
        frac = digits[1:] + '0' * max(0, decimals - len(digits) + 1)
        text = f'{sign}{digits[0]}.{frac}E{exp_:+d}'
    return text


def format_fixed(value: float, decimals: int) -> str:
    """
    Fixed-point with *decimals* decimals, more if needed to be exact.

    Used for ``:ACQ_TIME:`` (``854.8``) and ``:REC_TEMP:``.
    """
    value = float(value)
    special = _special(value)
    if special is not None:
        return special
    text = '%.*f' % (decimals, value)
    if float(text) != value:
        text = repr(value)
        if 'e' in text or 'E' in text:
            text = format_sci(value, decimals)
    return text


__all__ = ['format_eng', 'format_eng_exact', 'format_sci', 'format_fixed']
