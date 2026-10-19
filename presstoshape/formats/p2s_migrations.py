"""Upgrades document.json payloads from older .p2s format versions, one version step at a time.

Rule: every change to what .p2s files store bumps CURRENT_VERSION, adds MIGRATIONS[old_version] turning an
old payload into the next version's shape, and adds tests/formats/samples/v<old_version>.p2s to the tests.
"""

from collections.abc import Callable
from typing import Any

CURRENT_VERSION = 3


def _add_unit_and_dpi(payload: dict[str, Any]) -> dict[str, Any]:
    """Version 2 documents carry a display unit and DPI; version 1 documents were plain pixels at 96 DPI."""
    document = payload.get("document")
    if isinstance(document, dict):
        payload = {**payload, "document": {"unit": "px", "dpi": 96.0, **document}}
    return payload


def _unchanged(payload: dict[str, Any]) -> dict[str, Any]:
    """Version 3 only added the optional `tools.pencil_smoothing`; version 2 files need no change."""
    return payload


# MIGRATIONS[n] turns a version-n payload into a version-(n + 1) payload.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _add_unit_and_dpi, 2: _unchanged}


def upgrade(payload: dict[str, Any], version: int) -> dict[str, Any]:
    for step in range(version, CURRENT_VERSION):
        payload = MIGRATIONS[step](payload)
    return payload
