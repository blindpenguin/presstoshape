"""Upgrades document.json payloads from older .p2s format versions, one version step at a time.

Rule: every change to what .p2s files store bumps CURRENT_VERSION, adds MIGRATIONS[old_version] turning an
old payload into the next version's shape, and adds tests/formats/samples/v<old_version>.p2s to the tests.
"""

from collections.abc import Callable
from typing import Any

CURRENT_VERSION = 1

# MIGRATIONS[n] turns a version-n payload into a version-(n + 1) payload.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def upgrade(payload: dict[str, Any], version: int) -> dict[str, Any]:
    for step in range(version, CURRENT_VERSION):
        payload = MIGRATIONS[step](payload)
    return payload
