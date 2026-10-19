"""Where user settings live: the platform's usual place (registry on Windows, ~/.config on Linux), or, for the
portable Windows build, an INI file next to the executable so nothing is written outside its folder."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

# Shipped only in the portable ZIP; its presence switches a packaged build to settings beside the executable.
PORTABLE_MARKER = "portable.txt"
PORTABLE_SETTINGS = "settings.ini"
PORTABLE_TRANSLATIONS = "translations"
RENDERERS = ("auto", "gl", "cpu")
_LANGUAGE_KEY = "language"
_RENDERER_KEY = "renderer"


def _portable_folder(executable: str, frozen: bool) -> Path | None:
    folder = Path(executable).resolve().parent
    return folder if frozen and (folder / PORTABLE_MARKER).is_file() else None


def open_settings(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> QSettings:
    portable = _portable_folder(executable, frozen)
    if portable is not None:
        return QSettings(str(portable / PORTABLE_SETTINGS), QSettings.Format.IniFormat)
    return QSettings("PressToShape", "PressToShape")


def translations_folder(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> Path:
    """Where user translation files live: next to the portable executable, else the platform's app data folder
    (e.g. ~/.local/share/PressToShape/PressToShape on Linux). It may not exist yet."""
    portable = _portable_folder(executable, frozen)
    if portable is not None:
        return portable / PORTABLE_TRANSLATIONS
    location = QStandardPaths.StandardLocation.GenericDataLocation
    return Path(QStandardPaths.writableLocation(location)) / "PressToShape" / "PressToShape" / "translations"


def language(settings: QSettings) -> str | None:
    """The chosen language code; None means the system language."""
    value = settings.value(_LANGUAGE_KEY)
    return value if isinstance(value, str) and value else None


def set_language(settings: QSettings, code: str | None) -> None:
    if code is None:
        settings.remove(_LANGUAGE_KEY)
    else:
        settings.setValue(_LANGUAGE_KEY, code)


def renderer(settings: QSettings) -> str:
    value = settings.value(_RENDERER_KEY)
    return value if value in RENDERERS else "auto"


def set_renderer(settings: QSettings, value: str) -> None:
    if value not in RENDERERS:
        raise ValueError(f"unknown renderer {value!r}")
    settings.setValue(_RENDERER_KEY, value)
