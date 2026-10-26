from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QContextMenuEvent, QHelpEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from presstoshape.i18n import _
from presstoshape.views.paint_pair import checkerboard

_CELL = 18
_GAP = 3


@dataclass(frozen=True)
class Cell:
    # What the signals hand back: a swatch id or a colour.
    key: object
    color: str
    opacity: float = 1.0
    tooltip: str = ""


class SwatchGrid(QWidget):
    """Colour squares in rows that wrap to the width. Emits `picked(key)` on a click, `menu_requested(key, global
    position)` on a right click (key None on empty space) and `add_requested()` from the optional "+" cell."""

    picked = Signal(object)
    menu_requested = Signal(object, QPoint)
    add_requested = Signal()

    def __init__(self, add_tooltip: str = "") -> None:
        super().__init__()
        self._cells: tuple[Cell, ...] = ()
        self._add_tooltip = add_tooltip
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def set_cells(self, cells: tuple[Cell, ...]) -> None:
        if cells != self._cells:
            count_changed = len(cells) != len(self._cells)
            self._cells = cells
            if count_changed:
                self.updateGeometry()
            self.update()

    @property
    def cells(self) -> tuple[Cell, ...]:
        return self._cells

    def _count(self) -> int:
        return len(self._cells) + (1 if self._add_tooltip else 0)

    def _columns(self, width: int) -> int:
        return max(1, (width + _GAP) // (_CELL + _GAP))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        rows = max(1, -(-self._count() // self._columns(width)))
        return rows * (_CELL + _GAP) - _GAP + 2

    def sizeHint(self) -> QSize:
        return QSize(8 * (_CELL + _GAP), self.heightForWidth(8 * (_CELL + _GAP)))

    def minimumSizeHint(self) -> QSize:
        return QSize(_CELL + 2, _CELL + 2)

    def _rect(self, index: int) -> QRectF:
        columns = self._columns(self.width())
        row, column = divmod(index, columns)
        return QRectF(1 + column * (_CELL + _GAP) + 0.5, 1 + row * (_CELL + _GAP) + 0.5, _CELL - 1, _CELL - 1)

    def _index_at(self, position: QPointF) -> int | None:
        for index in range(self._count()):
            if self._rect(index).adjusted(-1, -1, 1, 1).contains(position):
                return index
        return None

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QPen(QColor("#52525b"), 1)
        for index, cell in enumerate(self._cells):
            rect = self._rect(index)
            painter.setPen(Qt.PenStyle.NoPen)
            if cell.opacity < 1:
                painter.setBrush(checkerboard())
                painter.drawRoundedRect(rect, 2, 2)
            color = QColor(cell.color)
            color.setAlphaF(cell.opacity)
            painter.setBrush(color)
            painter.setPen(border)
            painter.drawRoundedRect(rect, 2, 2)
        if self._add_tooltip:
            rect = self._rect(len(self._cells))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#a1a1aa"), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect, 2, 2)
            painter.setPen(QPen(QColor("#d4d4d8"), 1.5))
            center = rect.center()
            painter.drawLine(QPointF(center.x() - 4, center.y()), QPointF(center.x() + 4, center.y()))
            painter.drawLine(QPointF(center.x(), center.y() - 4), QPointF(center.x(), center.y() + 4))
        painter.end()

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            index = self._index_at(QPointF(event.pos()))
            if index is None:
                QToolTip.hideText()
            elif index < len(self._cells):
                QToolTip.showText(event.globalPos(), self._cells[index].tooltip, self)
            else:
                QToolTip.showText(event.globalPos(), self._add_tooltip, self)
            return True
        return super().event(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self._index_at(event.position())
        if index is None:
            return
        if index < len(self._cells):
            self.picked.emit(self._cells[index].key)
        else:
            self.add_requested.emit()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        index = self._index_at(QPointF(event.pos()))
        key = self._cells[index].key if index is not None and index < len(self._cells) else None
        self.menu_requested.emit(key, event.globalPos())


def swatch_tooltip(name: str, color: str, opacity: float) -> str:
    text = f"{name} – {color}" if name else color
    if opacity < 1:
        text += " " + _("({percent} % opaque)").format(percent=round(opacity * 100))
    return text
