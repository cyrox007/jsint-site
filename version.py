from __future__ import annotations

from pathlib import Path

_VERSION_FILE = Path(__file__).with_name("VERSION")


def application_version() -> str:
    try:
        value = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return value or "unknown"
