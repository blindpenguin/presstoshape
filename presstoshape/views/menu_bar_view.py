from PySide6.QtWidgets import QMenu, QMenuBar

from presstoshape.i18n import _
from presstoshape.views.actions import AppActions
from presstoshape.views.keymap import MENUS, RECENT_MENU, RECENT_MENU_TITLE


def build(menu_bar: QMenuBar, actions: AppActions) -> QMenu:
    """Builds the menus; returns the (empty) recent files submenu for the window to fill."""
    recent: list[QMenu] = []
    for title, entries in MENUS:
        _fill(menu_bar.addMenu(_(title)), entries, actions, recent)
    return recent[0]


def _fill(menu: QMenu, entries, actions: AppActions, recent: list[QMenu]) -> None:
    for entry in entries:
        if entry is None:
            menu.addSeparator()
        elif entry == RECENT_MENU:
            recent.append(menu.addMenu(_(RECENT_MENU_TITLE)))
        elif isinstance(entry, tuple):
            title, sub_entries = entry
            _fill(menu.addMenu(_(title)), sub_entries, actions, recent)
        else:
            menu.addAction(actions[entry])
