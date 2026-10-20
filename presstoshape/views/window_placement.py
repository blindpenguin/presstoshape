"""Remembers the main window's size, position and maximized state between runs, and makes sure a restored window
lands where the user can reach it (monitor unplugged, resolution lowered, window dragged off-screen)."""

from PySide6.QtCore import QRect, QSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow

Box = tuple[int, int, int, int]  # x, y, width, height

DEFAULT_SIZE = (1100, 700)
# A window counts as reachable when this much of its top strip (where the title bar is) lies on a screen.
_GRIP_WIDTH = 120
_GRIP_HEIGHT = 30
_GEOMETRY_KEY = "window/geometry"
_MAXIMIZED_KEY = "window/maximized"
# Dock sizes, e.g. how the right sidebar is split between Layers and Align.
_DOCKS_KEY = "window/docks"


def _overlap(first: Box, second: Box) -> tuple[int, int]:
    width = min(first[0] + first[2], second[0] + second[2]) - max(first[0], second[0])
    height = min(first[1] + first[3], second[1] + second[3]) - max(first[1], second[1])
    return max(width, 0), max(height, 0)


def _centered(size: tuple[int, int], screen: Box) -> Box:
    width, height = min(size[0], screen[2]), min(size[1], screen[3])
    return screen[0] + (screen[2] - width) // 2, screen[1] + (screen[3] - height) // 2, width, height


def fit_on_screens(saved: Box | None, screens: list[Box]) -> Box:
    """Where to open the window. `screens` are available areas with the primary screen first. A reachable saved
    box is kept (shrunk and pulled in if its screen got smaller); otherwise the window is centered on the screen
    it overlaps most, or on the primary screen."""
    primary = screens[0]
    if saved is None or saved[2] <= 0 or saved[3] <= 0:
        return _centered(DEFAULT_SIZE, primary)
    title_strip = (saved[0], saved[1], saved[2], _GRIP_HEIGHT)
    for screen in screens:
        width, height = _overlap(title_strip, screen)
        if width >= min(_GRIP_WIDTH, saved[2]) and height >= _GRIP_HEIGHT:
            if saved[2] <= screen[2] and saved[3] <= screen[3]:
                return saved
            x, y, width, height = saved[0], saved[1], min(saved[2], screen[2]), min(saved[3], screen[3])
            x = min(max(x, screen[0]), screen[0] + screen[2] - width)
            y = min(max(y, screen[1]), screen[1] + screen[3] - height)
            return x, y, width, height
    best = max(screens, key=lambda screen: _overlap(saved, screen)[0] * _overlap(saved, screen)[1])
    if _overlap(saved, best) == (0, 0):
        best = primary
    return _centered((saved[2], saved[3]), best)


def _screens() -> list[Box]:
    primary = QGuiApplication.primaryScreen()
    ordered = [primary] + [screen for screen in QGuiApplication.screens() if screen is not primary]
    return [screen.availableGeometry().getRect() for screen in ordered]


def _saved_box(settings: QSettings) -> Box | None:
    value = settings.value(_GEOMETRY_KEY)
    try:
        box = tuple(int(part) for part in value)
    except (TypeError, ValueError):
        return None
    return box if len(box) == 4 else None


def show(window: QMainWindow, settings: QSettings) -> None:
    """Shows `window` where it was last closed (maximized again if it was), with its panels as they were."""
    window.setGeometry(QRect(*fit_on_screens(_saved_box(settings), _screens())))
    state = settings.value(_DOCKS_KEY)
    if state is not None:
        window.restoreState(state)
    if settings.value(_MAXIMIZED_KEY, False, type=bool):
        window.showMaximized()
    else:
        window.show()


def save(window: QMainWindow, settings: QSettings) -> None:
    # normalGeometry is the restored size even while maximized, so un-maximizing after a restart works.
    settings.setValue(_GEOMETRY_KEY, list(window.normalGeometry().getRect()))
    settings.setValue(_MAXIMIZED_KEY, window.isMaximized())
    settings.setValue(_DOCKS_KEY, window.saveState())
