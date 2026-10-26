"""Stored palettes on disk: one JSON file per palette and an index with their order. Text in, text out; the
store in views reads and writes the files."""

import json
import re
from collections.abc import Iterable
from typing import Any

from presstoshape.formats.swatch_library import read_library, write_library
from presstoshape.models.colours import Palette, Swatch

VERSION = 1
INDEX_FILE = "index.json"
_UNSAFE = re.compile(r"[^a-z0-9._-]+")
_MAX_STEM = 60


def encode_palette(palette: Palette) -> str:
    payload = json.loads(write_library(palette.swatches))
    return (
        json.dumps(
            {"version": VERSION, "name": palette.name, "swatches": payload["swatches"]}, indent=1, ensure_ascii=False
        )
        + "\n"
    )


def decode_palette(text: str) -> tuple[str, tuple[Swatch, ...]]:
    """The palette's name and swatches (numbered from 1). Raises ValueError for anything else."""
    swatches = read_library(text)
    name = json.loads(text).get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("palette without a name")
    return " ".join(name.split()), swatches


def encode_index(files: Iterable[str]) -> str:
    return json.dumps({"version": VERSION, "order": list(files)}, indent=1, ensure_ascii=False) + "\n"


def decode_index(text: str) -> list[str]:
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"not JSON: {error}") from None
    order = payload.get("order") if isinstance(payload, dict) else None
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ValueError("not a palette index")
    return order


def file_name(name: str, taken: Iterable[str], suffix: str = ".json") -> str:
    """A file name for a palette called `name`, safe on every system and not in `taken` (compared without case,
    as Windows and macOS do): lower case, other characters as `-`, numbered if needed."""
    stem = _UNSAFE.sub("-", name.casefold()).strip("-.")[:_MAX_STEM].strip("-.") or "palette"
    used = {item.casefold() for item in taken}
    candidate, number = f"{stem}{suffix}", 1
    while candidate.casefold() in used or candidate.casefold() == INDEX_FILE:
        number += 1
        candidate = f"{stem}-{number}{suffix}"
    return candidate
