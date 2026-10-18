from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QToolButton, QVBoxLayout, QWidget

from veccy import icons
from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState
from veccy.views.icon_engine import icon


class LayersPanel(QWidget):
    """Layer list, topmost first. Checkbox = visibility, double-click = rename."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._controller = controller
        self._shown: tuple | None = None
        self._count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        buttons = QHBoxLayout()
        self._add = self._button(icons.LAYER_ADD, "Add layer", controller.add_layer)
        self._delete = self._button(
            icons.LAYER_DELETE, "Delete layer", lambda: controller.remove_layer(controller.state.selected_layer_index)
        )
        buttons.addWidget(self._add)
        buttons.addWidget(self._delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._list = QListWidget()
        layout.addWidget(self._list)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.currentRowChanged.connect(lambda row: controller.select_layer(self._index(row)))

    @staticmethod
    def _button(path, tooltip, slot) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(path))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.clicked.connect(lambda: slot())
        return button

    def _index(self, row: int) -> int:
        return self._count - 1 - row

    def refresh(self, state: AppState) -> None:
        layers = state.document.layers
        shown = tuple((layer.name, layer.visible) for layer in layers)
        self._list.blockSignals(True)
        # Rebuilding resets an in-progress rename and scroll position, so only do it when layers changed.
        if shown != self._shown:
            self._shown = shown
            self._count = len(layers)
            self._list.clear()
            for layer in reversed(layers):
                item = QListWidgetItem(layer.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
                self._list.addItem(item)
        self._list.setCurrentRow(self._index(state.selected_layer_index))
        self._list.blockSignals(False)
        self._delete.setEnabled(len(layers) > 1)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        index = self._index(self._list.row(item))
        visible = item.checkState() == Qt.CheckState.Checked
        name = item.text()
        self._shown = None
        # Deferred: the controller's notify rebuilds this list, which must not happen inside the item's own signal.
        QTimer.singleShot(0, lambda: self._apply(index, visible, name))

    def _apply(self, index: int, visible: bool, name: str) -> None:
        self._controller.set_layer_visible(index, visible)
        self._controller.rename_layer(index, name)
