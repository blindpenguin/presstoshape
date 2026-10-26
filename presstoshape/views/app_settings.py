"""Where user settings live: the platform's usual place (registry on Windows, ~/.config on Linux), or, for the
portable Windows build, an INI file next to the executable so nothing is written outside its folder."""

import re
import sys
from dataclasses import fields
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from presstoshape.editing.operations.documents import DocumentSetup, setup_problem
from presstoshape.models.colours import RECENT_LIMIT as RECENT_COLOURS_LIMIT
from presstoshape.models.colours import NumberMode
from presstoshape.models.layout import SnapSettings

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
_RECOVERY_KEY = "recovery/interval_minutes"
_BACKUPS_KEY = "save/keep_backups"
# Recovery snapshot intervals offered in Settings, in minutes; 0 turns recovery off.
RECOVERY_INTERVALS = (0, 1, 2, 5, 10)
DEFAULT_RECOVERY_INTERVAL = 5
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


def _data_folder(name: str, executable: str, frozen: bool) -> Path:
    """`name` next to the portable executable, else in the platform's app data folder
    (e.g. ~/.local/share/PressToShape/PressToShape on Linux). It may not exist yet."""
    portable = _portable_folder(executable, frozen)
    if portable is not None:
        return portable / name
    location = QStandardPaths.StandardLocation.GenericDataLocation
    return Path(QStandardPaths.writableLocation(location)) / "PressToShape" / "PressToShape" / name


def translations_folder(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> Path:
    """Where user translation files live."""
    return _data_folder(PORTABLE_TRANSLATIONS, executable, frozen)


def recovery_folder(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> Path:
    """Where crash recovery snapshots live; never one of the user's own folders."""
    return _data_folder("recovery", executable, frozen)


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


# --- crash recovery and backups ----------------------------------------------------------------------


def recovery_interval(settings: QSettings) -> int:
    """Minutes between recovery snapshots; 0 = off."""
    try:
        value = int(settings.value(_RECOVERY_KEY, DEFAULT_RECOVERY_INTERVAL))
    except (TypeError, ValueError):
        return DEFAULT_RECOVERY_INTERVAL
    return value if value in RECOVERY_INTERVALS else DEFAULT_RECOVERY_INTERVAL


def set_recovery_interval(settings: QSettings, minutes: int) -> None:
    if minutes not in RECOVERY_INTERVALS:
        raise ValueError(f"unsupported recovery interval {minutes!r}")
    settings.setValue(_RECOVERY_KEY, minutes)


def keep_backups(settings: QSettings) -> bool:
    return settings.value(_BACKUPS_KEY, True) not in (False, "false", "0", 0)


def set_keep_backups(settings: QSettings, value: bool) -> None:
    settings.setValue(_BACKUPS_KEY, value)


_RULERS_KEY = "view/showRulers"
_SNAP_GROUP = "snapping"


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    return value not in (False, "false", "0", 0)


def show_rulers(settings: QSettings) -> bool:
    return _as_bool(settings.value(_RULERS_KEY), True)


def set_show_rulers(settings: QSettings, value: bool) -> None:
    settings.setValue(_RULERS_KEY, value)


def snap_settings(settings: QSettings) -> SnapSettings:
    """Snapping switches and distance; missing or broken values keep their defaults."""
    defaults = SnapSettings()
    values = {}
    for field in fields(SnapSettings):
        stored = settings.value(f"{_SNAP_GROUP}/{field.name}")
        if field.name == "distance_px":
            try:
                values[field.name] = min(30.0, max(2.0, float(stored)))
            except (TypeError, ValueError):
                values[field.name] = defaults.distance_px
        else:
            values[field.name] = _as_bool(stored, getattr(defaults, field.name))
    return SnapSettings(**values)


def set_snap_settings(settings: QSettings, snapping: SnapSettings) -> None:
    for field in fields(SnapSettings):
        settings.setValue(f"{_SNAP_GROUP}/{field.name}", getattr(snapping, field.name))


# --- colours ----------------------------------------------------------------------------------------

_RECENT_COLOURS_KEY = "colours/recent"
_COLOUR_NUMBERS_KEY = "colours/numbers"
_HEX_COLOUR = re.compile(r"#[0-9a-f]{6}")


def recent_colours(settings: QSettings) -> tuple[str, ...]:
    value = settings.value(_RECENT_COLOURS_KEY)
    entries = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    colors = [entry.lower() for entry in entries if isinstance(entry, str) and _HEX_COLOUR.fullmatch(entry.lower())]
    return tuple(dict.fromkeys(colors))[:RECENT_COLOURS_LIMIT]


def set_recent_colours(settings: QSettings, colors: tuple[str, ...]) -> None:
    if colors:
        settings.setValue(_RECENT_COLOURS_KEY, list(colors))
    else:
        settings.remove(_RECENT_COLOURS_KEY)


def colour_numbers(settings: QSettings) -> NumberMode:
    return "rgb" if settings.value(_COLOUR_NUMBERS_KEY) == "rgb" else "hsv"


def set_colour_numbers(settings: QSettings, mode: NumberMode) -> None:
    settings.setValue(_COLOUR_NUMBERS_KEY, mode)


def swatch_library_path(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> Path:
    """The personal swatch library file; the folder may not exist yet."""
    return _data_folder("swatches.json", executable, frozen)
