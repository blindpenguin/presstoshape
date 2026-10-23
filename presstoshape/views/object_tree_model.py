"""Item model behind the Layers panel's tree: layers topmost first, their objects under them topmost first, and
the children of groups and parts of Composites under those. Rows are made only when the view asks for them, so
collapsed groups cost nothing. Changes are applied row by row rather than by a reset: an expanded layer with
thousands of objects would otherwise be laid out again after every edit."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QFont, QIcon

from presstoshape import icons
from presstoshape.editing import object_tree
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState, Layer
from presstoshape.models.shapes import GroupShape, Shape, children_of
from presstoshape.views.icon_engine import icon

NAME_COLUMN, EYE_COLUMN, LOCK_COLUMN = 0, 1, 2

_TYPE_ICONS = {
    "rect": icons.OBJECT_RECT,
    "ellipse": icons.OBJECT_ELLIPSE,
    "path": icons.OBJECT_PATH,
    "text": icons.OBJECT_TEXT,
    "group": icons.OBJECT_GROUP,
    "composite": icons.OBJECT_COMPOSITE,
    "clip": icons.OBJECT_CLIP,
    "mask": icons.OBJECT_MASK,
}

Index = QModelIndex | QPersistentModelIndex


def _masking_of(shape: Shape):
    return shape.masking if isinstance(shape, GroupShape) else None


@dataclass(eq=False)
class TreeNode:
    """One row: a layer (`shape` None) or an object. `hidden` / `locked` are its own flags, `inherited_*` what
    the layer and containers around it add. `shapes` are its children, bottom to top as stored."""

    layer_index: int
    shape: Shape | None
    parent: "TreeNode | None"
    row: int
    name: str
    hidden: bool
    locked: bool
    inherited_hidden: bool
    inherited_locked: bool
    shapes: Sequence[Shape]
    # Child rows made so far, by row.
    children: dict[int, "TreeNode"] = field(default_factory=dict)
    # Row of each child id, made on the first lookup by id.
    rows: dict[int, int] | None = None

    @property
    def shown_hidden(self) -> bool:
        return self.hidden or self.inherited_hidden

    @property
    def shown_locked(self) -> bool:
        return self.locked or self.inherited_locked


class ObjectTreeModel(QAbstractItemModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layers: list[TreeNode] = []
        # Layer index and container ids of every object, made on the first lookup by id.
        self._locations: dict[int, object_tree.Location] | None = None
        # Called with (layer index, new name) when a layer name is edited in the view.
        self.on_rename: Callable[[int, str], None] | None = None
        self._icons: dict[tuple, QIcon] = {}
        self._active_layer = 0
        # Set when rows were added, removed or reset; the panel then selects the selected objects' rows again.
        self.rows_replaced = False
        self._bold = QFont()
        self._bold.setBold(True)

    # --- content ------------------------------------------------------------------------------------

    def set_content(self, state: AppState) -> None:
        """Shows the document's layers. Unchanged shape objects (frozen, so unchanged shapes) cost one identity
        check each; a different number of layers resets the model, anything else updates the changed rows."""
        layers = state.document.layers
        if len(layers) != len(self._layers):
            self.beginResetModel()
            self._layers = [self._layer_node(layers, index) for index in range(len(layers))]
            self._locations = None
            self.rows_replaced = True
            self.endResetModel()
            return
        for node, layer in zip(self._layers, layers):
            hidden, locked = not layer.visible, layer.locked
            flags_changed = (node.hidden, node.locked) != (hidden, locked)
            if node.name != layer.name or flags_changed:
                node.name, node.hidden, node.locked = layer.name, hidden, locked
                self._changed(node, node)
            if flags_changed or _differ(node.shapes, layer.shapes):
                self._sync(node, list(layer.shapes))

    def set_active_layer(self, layer_index: int) -> None:
        """The active layer's name is shown bold."""
        if layer_index == self._active_layer:
            return
        previous, self._active_layer = self._active_layer, layer_index
        for index in (previous, layer_index):
            if 0 <= index < len(self._layers):
                self._changed(self._layers[index], self._layers[index])

    def _layer_node(self, layers: list[Layer], layer_index: int) -> TreeNode:
        layer = layers[layer_index]
        row = len(layers) - 1 - layer_index
        return TreeNode(
            layer_index, None, None, row, layer.name, not layer.visible, layer.locked, False, False, list(layer.shapes)
        )

    def _sync(self, parent: TreeNode, shapes: Sequence[Shape]) -> None:
        """Brings `parent`'s children up to `shapes`: rows between the unchanged bottom and top ids are removed
        and inserted again, the others are updated in place."""
        old = parent.shapes
        old_count, new_count = len(old), len(shapes)
        bottom = 0
        while bottom < min(old_count, new_count) and old[bottom].id == shapes[bottom].id:
            bottom += 1
        top = 0
        limit = min(old_count, new_count) - bottom
        while top < limit and old[old_count - 1 - top].id == shapes[new_count - 1 - top].id:
            top += 1
        if bottom + top != old_count or old_count != new_count:
            self._replace_rows(parent, shapes, bottom, top)
        else:
            parent.shapes = shapes
        changed = [
            child
            for child in parent.children.values()
            if self._refresh(child, shapes[new_count - 1 - child.row], parent.shown_hidden, parent.shown_locked)
        ]
        if changed:
            self._changed(min(changed, key=lambda node: node.row), max(changed, key=lambda node: node.row))

    def _replace_rows(self, parent: TreeNode, shapes: Sequence[Shape], bottom: int, top: int) -> None:
        """Rows are topmost first: the `top` unchanged ones keep rows 0..top-1, the `bottom` unchanged ones move
        by the difference in count, everything between is replaced."""
        parent_index = self._index_of(parent)
        old_count, new_count = len(parent.shapes), len(shapes)
        removed = old_count - bottom - top
        if removed:
            self.beginRemoveRows(parent_index, top, top + removed - 1)
            parent.shapes = [*parent.shapes[:bottom], *parent.shapes[old_count - top :]]
            parent.children = {
                (row if row < top else row - removed): node
                for row, node in parent.children.items()
                if row < top or row >= top + removed
            }
            for row, node in parent.children.items():
                node.row = row
            self.endRemoveRows()
        inserted = new_count - bottom - top
        if inserted:
            self.beginInsertRows(parent_index, top, top + inserted - 1)
            parent.shapes = shapes
            parent.children = {(row if row < top else row + inserted): node for row, node in parent.children.items()}
            for row, node in parent.children.items():
                node.row = row
            self.endInsertRows()
        parent.shapes = shapes
        parent.rows = None
        self._locations = None
        self.rows_replaced = True

    def _refresh(self, node: TreeNode, shape: Shape, inherited_hidden: bool, inherited_locked: bool) -> bool:
        """Points `node` at `shape` (same id) and updates its children; whether anything shown changed."""
        if node.shape is shape and (node.inherited_hidden, node.inherited_locked) == (
            inherited_hidden,
            inherited_locked,
        ):
            return False
        previous = node.shape
        node.shape = shape
        node.hidden, node.locked = shape.hidden, shape.locked
        node.inherited_hidden, node.inherited_locked = inherited_hidden, inherited_locked
        self._sync(node, children_of(shape))
        if previous is not None and _masking_of(previous) != _masking_of(shape) and node.shapes:
            # Which children are mask objects changed without the children themselves changing.
            parent_index = self._index_of(node)
            last_row = len(node.shapes) - 1
            self.dataChanged.emit(
                self.index(0, NAME_COLUMN, parent_index), self.index(last_row, NAME_COLUMN, parent_index)
            )
        return True

    @staticmethod
    def _role(node: TreeNode) -> object_tree.ChildRole | None:
        parent = node.parent
        if parent is None or parent.shape is None or node.shape is None:
            return None
        return object_tree.child_role(parent.shape, node.shape.id)

    def _changed(self, first: TreeNode, last: TreeNode) -> None:
        """Rows `first` to `last` of one parent changed."""
        self.dataChanged.emit(
            self.createIndex(first.row, NAME_COLUMN, first), self.createIndex(last.row, LOCK_COLUMN, last)
        )

    def _index_of(self, node: TreeNode) -> QModelIndex:
        return self.createIndex(node.row, NAME_COLUMN, node)

    # --- lookups ------------------------------------------------------------------------------------

    def node(self, index: Index) -> TreeNode | None:
        return index.internalPointer() if index.isValid() else None

    def layer_index(self, layer_index: int) -> QModelIndex:
        if not 0 <= layer_index < len(self._layers):
            return QModelIndex()
        return self._index_of(self._layers[layer_index])

    def shape_index(self, shape_id: int) -> QModelIndex:
        """The row of an object anywhere in the tree (its parents' rows are made on the way), or invalid."""
        if self._locations is None:
            self._locations = _locations(self._layers)
        location = self._locations.get(shape_id)
        if location is None:
            return QModelIndex()
        index = self.layer_index(location.layer_index)
        for container_id in (*location.containers, shape_id):
            row = self._row_of(self.node(index), container_id)
            if row is None:
                return QModelIndex()
            index = self.index(row, NAME_COLUMN, index)
        return index

    def _row_of(self, parent: TreeNode, shape_id: int) -> int | None:
        if parent.rows is None:
            count = len(parent.shapes)
            parent.rows = {shape.id: count - 1 - position for position, shape in enumerate(parent.shapes)}
        return parent.rows.get(shape_id)

    def _child_node(self, parent: TreeNode, row: int) -> TreeNode:
        node = parent.children.get(row)
        if node is None:
            shape = parent.shapes[len(parent.shapes) - 1 - row]
            node = TreeNode(
                parent.layer_index,
                shape,
                parent,
                row,
                "",
                shape.hidden,
                shape.locked,
                parent.shown_hidden,
                parent.shown_locked,
                children_of(shape),
            )
            parent.children[row] = node
        return node

    # --- QAbstractItemModel -------------------------------------------------------------------------

    # The view calls these for every row of an expanded layer when it lays rows out, so they stay lean.

    def index(self, row: int, column: int, parent: Index = QModelIndex()) -> QModelIndex:
        if not 0 <= column < 3:
            return QModelIndex()
        if not parent.isValid():
            if not 0 <= row < len(self._layers):
                return QModelIndex()
            return self.createIndex(row, column, self._layers[len(self._layers) - 1 - row])
        parent_node = parent.internalPointer()
        if parent.column() != NAME_COLUMN or not 0 <= row < len(parent_node.shapes):
            return QModelIndex()
        node = parent_node.children.get(row) or self._child_node(parent_node, row)
        return self.createIndex(row, column, node)

    def parent(self, index: Index = QModelIndex()) -> QModelIndex:  # type: ignore[override]
        node = self.node(index)
        if node is None or node.parent is None:
            return QModelIndex()
        return self._index_of(node.parent)

    def rowCount(self, parent: Index = QModelIndex()) -> int:
        if not parent.isValid():
            return len(self._layers)
        if parent.column() != NAME_COLUMN:
            return 0
        return len(parent.internalPointer().shapes)

    def hasChildren(self, parent: Index = QModelIndex()) -> bool:
        if not parent.isValid():
            return bool(self._layers)
        return parent.column() == NAME_COLUMN and bool(parent.internalPointer().shapes)

    def columnCount(self, parent: Index = QModelIndex()) -> int:
        return 3

    def flags(self, index: Index) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() == NAME_COLUMN and index.internalPointer().shape is None:
            return _LAYER_NAME_FLAGS
        return _FLAGS

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole):
        node = self.node(index)
        if node is None:
            return None
        column = index.column()
        if column == NAME_COLUMN:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return node.name if node.shape is None else object_tree.object_label(node.shape, self._role(node))
            if role == Qt.ItemDataRole.DecorationRole and node.shape is not None:
                return self._icon(_TYPE_ICONS[object_tree.object_type(node.shape)], node.shown_hidden)
            if role == Qt.ItemDataRole.FontRole and node.shape is None and node.layer_index == self._active_layer:
                return self._bold
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == EYE_COLUMN:
                return _("Show") if node.hidden else _("Hide")
            return _("Unlock") if node.locked else _("Lock")
        if role != Qt.ItemDataRole.DecorationRole:
            return None
        # Dimmed: the state comes only from the layer or a container around the object.
        if column == EYE_COLUMN:
            path = icons.HIDDEN if node.shown_hidden else icons.VISIBLE
            return self._icon(path, node.shown_hidden and not node.hidden)
        path = icons.LOCKED if node.shown_locked else icons.UNLOCKED
        return self._icon(path, node.shown_locked and not node.locked)

    def setData(self, index: Index, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        node = self.node(index)
        if node is None or node.shape is not None or role != Qt.ItemDataRole.EditRole or self.on_rename is None:
            return False
        self.on_rename(node.layer_index, str(value))
        return True

    def _icon(self, path, dimmed: bool) -> QIcon:
        key = (path, dimmed)
        if key not in self._icons:
            self._icons[key] = icon(path, dimmed, checkable=False)
        return self._icons[key]


_FLAGS = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
_LAYER_NAME_FLAGS = _FLAGS | Qt.ItemFlag.ItemIsEditable


def _differ(shown: Sequence[Shape], current: Sequence[Shape]) -> bool:
    return len(shown) != len(current) or any(a is not b for a, b in zip(shown, current))


def _locations(layers: list[TreeNode]) -> dict[int, object_tree.Location]:
    locations: dict[int, object_tree.Location] = {}
    for layer in layers:
        pending: list[tuple[Shape, tuple[int, ...]]] = [(shape, ()) for shape in layer.shapes]
        while pending:
            shape, around = pending.pop()
            locations[shape.id] = object_tree.Location(layer.layer_index, around)
            children = children_of(shape)
            if children:
                pending.extend((child, (*around, shape.id)) for child in children)
    return locations
