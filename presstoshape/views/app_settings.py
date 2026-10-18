"""Where user settings live: the platform's usual place (registry on Windows, ~/.config on Linux), or, for the
portable Windows build, an INI file next to the executable so nothing is written outside its folder."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

# Shipped only in the portable ZIP; its presence switches a packaged build to settings beside the executable.
PORTABLE_MARKER = "portable.txt"
PORTABLE_SETTINGS = "settings.ini"


def open_settings(executable: str = sys.executable, frozen: bool = getattr(sys, "frozen", False)) -> QSettings:
    folder = Path(executable).resolve().parent
    if frozen and (folder / PORTABLE_MARKER).is_file():
        return QSettings(str(folder / PORTABLE_SETTINGS), QSettings.Format.IniFormat)
    return QSettings("PressToShape", "PressToShape")
