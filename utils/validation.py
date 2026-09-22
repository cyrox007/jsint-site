from __future__ import annotations

import re

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_slug(value: str, *, max_length: int = 255) -> str:
    value = value.strip().lower()
    if not value or len(value) > max_length or SLUG_RE.fullmatch(value) is None:
        raise ValueError("URL должен содержать только латинские буквы, цифры и одиночные дефисы")
    return value
