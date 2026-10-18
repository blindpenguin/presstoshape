from PySide6.QtWidgets import QMenuBar

from veccy.views.actions import AppActions


def build(menu_bar: QMenuBar, actions: AppActions) -> None:
    file_menu = menu_bar.addMenu("&File")
    file_menu.addActions([actions.new, actions.open, actions.save, actions.save_as])
    file_menu.addSeparator()
    file_menu.addAction(actions.export_png)
    file_menu.addSeparator()
    file_menu.addAction(actions.quit)

    edit = menu_bar.addMenu("&Edit")
    edit.addActions([actions.undo, actions.redo])
    edit.addSeparator()
    edit.addActions([actions.select_all, actions.delete])

    path = menu_bar.addMenu("&Path")
    path.addActions([actions.union, actions.difference])
    path.addSeparator()
    path.addAction(actions.object_to_path)

    view = menu_bar.addMenu("&View")
    view.addActions([actions.zoom_in, actions.zoom_out, actions.zoom_fit, actions.zoom_actual])

    menu_bar.addMenu("&Tools").addActions(list(actions.tools.values()))

    menu_bar.addMenu("&Help").addAction(actions.about)
