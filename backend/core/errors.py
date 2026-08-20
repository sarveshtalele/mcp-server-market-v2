"""Shared error types.

Lives in its own module so modules can import it without pulling in
``core.data`` — which imports the module repositories, and would therefore
create an import cycle (module -> core.data -> module).
"""

from __future__ import annotations


class DataError(RuntimeError):
    """Raised when requested data does not exist.

    Tools catch this and return ``{"error": ...}``: a missing ticker is an
    ordinary answer ("no such company"), not a protocol-level failure.
    """
