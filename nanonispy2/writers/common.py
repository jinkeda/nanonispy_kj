"""
Helpers shared by the nanonispy2 writers.
"""

from pathlib import Path

from ..core.exceptions import UnhandledFileError


def check_target(fname, extension: str, overwrite: bool) -> None:
    """
    Validate an output path before anything is written.

    Parameters
    ----------
    fname : str or path-like
        Output file path.
    extension : str
        Required extension including the dot, e.g. ``'.sxm'``.
    overwrite : bool
        If False, an existing *fname* is an error.

    Raises
    ------
    UnhandledFileError
        If *fname* does not end with *extension*.
    FileExistsError
        If *fname* exists and *overwrite* is False.
    """
    if not str(fname).endswith(extension):
        raise UnhandledFileError(f"{fname} must have {extension} extension")
    if not overwrite and Path(fname).exists():
        raise FileExistsError(
            f"{fname} already exists. Set overwrite=True to replace it."
        )


def check_text_field(value: str, what: str, allow_tab: bool = False) -> str:
    """Reject line breaks (and optionally tabs) that would corrupt a header."""
    value = str(value)
    if '\n' in value or '\r' in value:
        raise ValueError(f"{what} must not contain line breaks: {value!r}")
    if not allow_tab and '\t' in value:
        raise ValueError(f"{what} must not contain tabs: {value!r}")
    return value


__all__ = ['check_target', 'check_text_field']
