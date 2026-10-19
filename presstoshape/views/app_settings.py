"""Where user settings live: the platform's usual place (registry on Windows, ~/.config on Linux), or, for the
portable Windows build, an INI file next to the executable so nothing is written outside its folder."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from presstoshape.editing.operations.documents import DocumentSetup, setup_problem

# Shipped only in the portable ZIP; its presence switches a packaged build to settings beside the executable.
PORTABLE_MARKER = "portable.txt"
PORTABLE_SETTINGS = "settings.ini"
PORTABLE_TRANSLATIONS = "translations"
RENDERERS = ("auto", "gl", "cpu")
RECENT_LIMIT = 10
_LANGUAGE_KEY = "language"
_RENDERER_KEY = "renderer"
_RECENT_KEY = "recent_files"
_START_DIALOG_KEY = "start/show_dialog"
_NEW_PRESET_KEY = "new_document/preset"
_NEW_SETUP_KEY = "new_document/setup"


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


# --- recent files -------------------------------------------------------------------------------


def updated_recent(paths: list[str], path: str, limit: int = RECENT_LIMIT) -> list[str]:
    """`path` (made absolute) first, without duplicates, at most `limit` entries."""
    resolved = str(Path(path).resolve())
    return [resolved, *(entry for entry in paths if entry != resolved)][:limit]


def recent_files(settings: QSettings) -> list[str]:
    value = settings.value(_RECENT_KEY)
    # INI files give back a one-entry list as a plain string.
    entries = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return [entry for entry in entries if isinstance(entry, str) and entry][:RECENT_LIMIT]


def add_recent_file(settings: QSettings, path: str) -> None:
    settings.setValue(_RECENT_KEY, updated_recent(recent_files(settings), path))


def remove_recent_file(settings: QSettings, path: str) -> None:
    settings.setValue(_RECENT_KEY, [entry for entry in recent_files(settings) if entry != path])


def clear_recent_files(settings: QSettings) -> None:
    settings.remove(_RECENT_KEY)


# --- start and new documents ----------------------------------------------------------------------


def show_start_dialog(settings: QSettings) -> bool:
    return settings.value(_START_DIALOG_KEY, True) not in (False, "false", "0", 0)


def set_show_start_dialog(settings: QSettings, value: bool) -> None:
    settings.setValue(_START_DIALOG_KEY, value)


def last_new_document(settings: QSettings) -> tuple[str | None, DocumentSetup] | None:
    """(preset id or None for custom, setup) of the last created document, if one is stored and still valid."""
    value = settings.value(_NEW_SETUP_KEY)
    try:
        width, height, unit, dpi = value
        setup = DocumentSetup(float(width), float(height), str(unit), float(dpi))
    except (TypeError, ValueError):
        return None
    if setup_problem(setup) is not None:
        return None
    preset = settings.value(_NEW_PRESET_KEY)
    return (preset if isinstance(preset, str) and preset else None), setup


def set_last_new_document(settings: QSettings, preset: str | None, setup: DocumentSetup) -> None:
    settings.setValue(_NEW_PRESET_KEY, preset or "")
    settings.setValue(_NEW_SETUP_KEY, [setup.width, setup.height, setup.unit, setup.dpi])
