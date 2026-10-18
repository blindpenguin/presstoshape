from PySide6.QtWidgets import QMenu, QMenuBar

from presstoshape.views.actions import AppActions
from presstoshape.views.keymap import MENUS


def build(menu_bar: QMenuBar, actions: AppActions) -> None:
    for title, entries in MENUS:
        _fill(menu_bar.addMenu(title), entries, actions)


def _fill(menu: QMenu, entries, actions: AppActions) -> None:
    for entry in entries:
        if entry is None:
            menu.addSeparator()
        elif isinstance(entry, tuple):
            title, sub_entries = entry
            _fill(menu.addMenu(title), sub_entries, actions)
        else:
            menu.addAction(actions[entry])
