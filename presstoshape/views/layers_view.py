from functools import partial

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from presstoshape import icons
from presstoshape.editing import containers
from presstoshape.editing.operations import layers, selection, visibility
from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.views.icon_engine import icon
from presstoshape.views.object_tree_model import EYE_COLUMN, LOCK_COLUMN, NAME_COLUMN, ObjectTreeModel, TreeNode

_TOGGLE_COLUMN_WIDTH = 24


class _ObjectTree(QTreeView):
    """Clicks on the eye and lock columns toggle instead of selecting the row."""

    toggle_clicked = Signal(QModelIndex)

    def _toggle(self, event: QMouseEvent) -> bool:
        index = self.indexAt(event.position().toPoint())
        if event.button() != Qt.MouseButton.LeftButton or index.column() not in (EYE_COLUMN, LOCK_COLUMN):
            return False
        self.toggle_clicked.emit(index)
        event.accept()
        return True

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._toggle(event):
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # The second click of a quick double click toggles again rather than getting lost.
        if not self._toggle(event):
            super().mouseDoubleClickEvent(event)


class LayersPanel(QWidget):
    """Layers and their objects as a tree, topmost first: eye and lock toggles on every row, a click on an object
    selects it (entering the groups around it), double-click on a layer renames it."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._revision: int | None = None
        self._mirrored: tuple | None = None
        # Layers start expanded, groups and Composites collapsed; both are remembered while the panel lives.
        self._collapsed_layers: set[int] = set()
        self._expanded_shapes: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        buttons = QHBoxLayout()
        self._add = self._button(icons.LAYER_ADD, _("Add layer"), partial(layers.add_layer, session))
        self._delete = self._button(
            icons.LAYER_DELETE,
            _("Delete layer"),
            lambda: layers.remove_layer(session, session.state.selected_layer_index),
        )
        buttons.addWidget(self._add)
        buttons.addWidget(self._delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._model = ObjectTreeModel(self)
        self._model.on_rename = self._on_rename
        self._tree = _ObjectTree(self)
        self._tree.setModel(self._model)
        # After setModel, so the tree has handled the reset before expansion is restored.
        self._model.modelReset.connect(self._restore_expansion)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._tree.setIconSize(QSize(16, 16))
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(NAME_COLUMN, QHeaderView.ResizeMode.Stretch)
        for column in (EYE_COLUMN, LOCK_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, _TOGGLE_COLUMN_WIDTH)
        layout.addWidget(self._tree)
        self._tree.toggle_clicked.connect(self._on_toggle)
        self._tree.clicked.connect(self._on_clicked)
        self._tree.expanded.connect(lambda index: self._remember_expanded(index, True))
        self._tree.collapsed.connect(lambda index: self._remember_expanded(index, False))

    @staticmethod
    def _button(path, tooltip, slot) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(path))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.clicked.connect(lambda: slot())
        return button

    # --- refresh ------------------------------------------------------------------------------------

    def refresh(self, state: AppState) -> None:
        # Every document change bumps the revision; selection, tool and zoom changes don't.
        if self._session.revision != self._revision:
            self._revision = self._session.revision
            self._model.set_content(state)
        self._model.set_active_layer(state.selected_layer_index)
        mirrored = (frozenset(state.selection), containers.valid_edit_path(state))
        if mirrored != self._mirrored or self._model.rows_replaced:
            self._model.rows_replaced = False
            # Shown again only when the selection changed, not when the selected rows were edited.
            reveal = mirrored != self._mirrored
            self._mirrored = mirrored
            self._mirror_selection(state, reveal)
        self._delete.setEnabled(len(state.document.layers) > 1)

    def _mirror_selection(self, state: AppState, reveal: bool) -> None:
        indexes = [index for shape_id in state.selection if (index := self._model.shape_index(shape_id)).isValid()]
        rows = QItemSelection()
        # One range per run of neighbouring rows: thousands of one-row ranges make every later tree update slow.
        by_parent: dict[int, list[QModelIndex]] = {}
        for index in indexes:
            by_parent.setdefault(id(self._model.node(index).parent), []).append(index)
        for siblings in by_parent.values():
            siblings.sort(key=QModelIndex.row)
            start = previous = siblings[0]
            for index in [*siblings[1:], None]:
                if index is not None and index.row() == previous.row() + 1:
                    previous = index
                    continue
                rows.select(start, previous.siblingAtColumn(LOCK_COLUMN))
                if index is not None:
                    start = previous = index
        model = self._tree.selectionModel()
        model.blockSignals(True)
        model.select(rows, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        model.blockSignals(False)
        self._tree.viewport().update()
        if reveal and indexes:
            first = min(indexes, key=_row_path)
            parent = first.parent()
            while parent.isValid():
                self._tree.expand(parent)
                parent = parent.parent()
            self._tree.scrollTo(first)

    def _remember_expanded(self, index: QModelIndex, expanded: bool) -> None:
        node = self._model.node(index)
        if node.shape is None:
            (self._collapsed_layers.discard if expanded else self._collapsed_layers.add)(node.layer_index)
        else:
            (self._expanded_shapes.add if expanded else self._expanded_shapes.discard)(node.shape.id)

    def _restore_expansion(self) -> None:
        for layer_index in range(self._model.rowCount()):
            if layer_index not in self._collapsed_layers:
                self._tree.expand(self._model.layer_index(layer_index))
        for shape_id in list(self._expanded_shapes):
            index = self._model.shape_index(shape_id)
            if index.isValid():
                self._tree.expand(index)

    # --- input --------------------------------------------------------------------------------------
    # Deferred: the session's notify updates the tree, which must not happen inside the tree's own signals.

    def _on_toggle(self, index: QModelIndex) -> None:
        node = self._model.node(index)
        column = index.column()
        QTimer.singleShot(0, lambda: self._toggle(node, column))

    def _toggle(self, node: TreeNode, column: int) -> None:
        session = self._session
        if node.shape is None:
            if column == EYE_COLUMN:
                layers.set_layer_visible(session, node.layer_index, node.hidden)
            else:
                layers.set_layer_locked(session, node.layer_index, not node.locked)
        elif column == EYE_COLUMN:
            visibility.set_hidden(session, node.shape.id, not node.hidden)
        else:
            visibility.set_locked(session, node.shape.id, not node.locked)

    def _on_clicked(self, index: QModelIndex) -> None:
        node = self._model.node(index)
        if node.shape is None:
            QTimer.singleShot(0, lambda: self._select_layer(node.layer_index))
            return
        modifiers = QApplication.keyboardModifiers()
        extend = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
        # With Ctrl or Shift the tree has already toggled or extended its rows: take those of the same container.
        siblings = {
            sibling.shape.id
            for row in self._tree.selectionModel().selectedRows(NAME_COLUMN)
            if (sibling := self._model.node(row)).shape is not None and sibling.parent is node.parent
        }
        QTimer.singleShot(0, lambda: self._select(node.shape.id, siblings if extend else None))

    def _select_layer(self, layer_index: int) -> None:
        layers.select_layer(self._session, layer_index)
        # The tree selected the layer's row; the active layer is shown bold, the rows show the session's selection.
        self._mirrored = None
        self.refresh(self._session.state)

    def _select(self, shape_id: int, siblings: set[int] | None) -> None:
        if siblings is None:
            visibility.select_object(self._session, shape_id)
            return
        state = self._session.state
        if shape_id not in {shape.id for shape in containers.pickable_shapes(state)}:
            visibility.select_object(self._session, shape_id)
        selection.set_selection(self._session, siblings)
        # The tree shows the rows it selected even when some can't be picked; show the session's selection.
        self._mirrored = None
        self.refresh(state)

    def _on_rename(self, layer_index: int, name: str) -> None:
        QTimer.singleShot(0, lambda: layers.rename_layer(self._session, layer_index, name))


def _row_path(index: QModelIndex) -> tuple[int, ...]:
    """Rows from the top level down, so indexes sort in the order the tree shows them."""
    path = []
    while index.isValid():
        path.append(index.row())
        index = index.parent()
    return tuple(reversed(path))
