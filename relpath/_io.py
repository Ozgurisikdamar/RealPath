"""Console output helpers that never crash on a legacy code page (e.g. Windows cp1252)."""
from __future__ import annotations

import sys


def sprint(*args, sep: str = " ", end: str = "\n") -> None:
    """print() that degrades gracefully when the terminal can't encode a character."""
    text = sep.join(str(a) for a in args) + end
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, "replace").decode(enc))


def use_utf8() -> None:
    """Best-effort switch of stdout/stderr to UTF-8 (for CLI / demo entry points)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
