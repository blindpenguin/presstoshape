"""The app version: stamped into packaged builds, read from pyproject.toml when running from source."""

import importlib
import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def app_version() -> str:
    try:
        # Written by scripts/build_package.py before freezing; absent in a source checkout.
        build_info = importlib.import_module("presstoshape._build_info")
    except ImportError:
        pass
    else:
        return build_info.VERSION
    try:
        with _PYPROJECT.open("rb") as file:
            return tomllib.load(file)["project"]["version"] + " (source)"
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"
