from PySide6.QtWidgets import QMenuBar

from veccy.views.actions import AppActions
from veccy.views.keymap import MENUS


def build(menu_bar: QMenuBar, actions: AppActions) -> None:
    for title, entries in MENUS:
        menu = menu_bar.addMenu(title)
        for command_id in entries:
            if command_id is None:
                menu.addSeparator()
            else:
                menu.addAction(actions[command_id])
