"""The personal swatch library file (JSON): swatches shared by all documents, kept in the app's data folder."""

import json
import math
import re
from typing import Any

from presstoshape.models.colours import Swatch

VERSION = 1
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


def read_library(text: str) -> tuple[Swatch, ...]:
    """The library's swatches, numbered from 1. Raises ValueError for anything that isn't a readable library."""
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"not JSON: {error}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), int):
        raise ValueError("not a swatch library")
    if payload["version"] > VERSION:
        raise ValueError(f"library version {payload['version']} is newer than {VERSION}")
    items = payload.get("swatches")
    if not isinstance(items, list):
        raise ValueError("swatches should be a list")
    swatches = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"swatch {index} should be an object")
        color, name, opacity = item.get("color"), item.get("name", ""), item.get("opacity", 1.0)
        if not isinstance(color, str) or not _COLOR.fullmatch(color):
            raise ValueError(f"swatch {index} has no #rrggbb colour")
        if not isinstance(name, str):
            raise ValueError(f"swatch {index} has a name that isn't text")
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not math.isfinite(opacity):
            raise ValueError(f"swatch {index} has an opacity that isn't a number")
        swatches.append(Swatch(index + 1, name, color.lower(), min(1.0, max(0.0, float(opacity)))))
    return tuple(swatches)


def write_library(swatches: tuple[Swatch, ...]) -> str:
    items = []
    for swatch in swatches:
        item: dict[str, Any] = {"name": swatch.name, "color": swatch.color}
        if swatch.opacity != 1.0:
            item["opacity"] = swatch.opacity
        items.append(item)
    return json.dumps({"version": VERSION, "swatches": items}, indent=1, ensure_ascii=False) + "\n"
