"""Rulers along the canvas: ticks in the document's unit, the pointer position and the selection's extent.
Dragging out of a ruler creates a guide (the canvas runs that gesture)."""

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from presstoshape.geometry.rulers import ruler_ticks
from presstoshape.models.app_state import Unit
from presstoshape.models.layout import GuideOrientation
from presstoshape.views import theme

RULER_SIZE = 20
_MAJOR_TICK = 8
_MINOR_TICK = 4
_LABEL_POINT_SIZE = 7


class Ruler(QWidget):
    """`orientation` "horizontal" runs along the top edge, "vertical" along the left edge."""

    # Pressing on the ruler starts dragging out a guide; moves and the release come with global positions.
    guide_drag_started = Signal(str)
    guide_dragged = Signal(QPoint)
    guide_released = Signal(QPoint)

    def __init__(self, orientation: GuideOrientation, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.orientation = orientation
        self._start_doc = 0.0
        self._zoom = 1.0
        self._unit: Unit = "px"
        self._dpi = 96.0
        self._pointer: float | None = None
        self._extent: tuple[float, float] | None = None
        self._dragging = False
        self.setCursor(Qt.CursorShape.SplitVCursor if orientation == "horizontal" else Qt.CursorShape.SplitHCursor)

    def set_view(
        self,
        start_doc: float,
        zoom: float,
        unit: Unit,
        dpi: float,
        pointer: float | None,
        extent: tuple[float, float] | None,
    ) -> None:
        """`start_doc`: the document coordinate at the ruler's first pixel; `pointer` and `extent` in ruler
        pixels."""
        view = (start_doc, zoom, unit, dpi, pointer, extent)
        if view == (self._start_doc, self._zoom, self._unit, self._dpi, self._pointer, self._extent):
            return
        self._start_doc, self._zoom, self._unit, self._dpi, self._pointer, self._extent = view
        self.update()

    def _length(self) -> int:
        return self.width() if self.orientation == "horizontal" else self.height()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.window())
        horizontal = self.orientation == "horizontal"
        if self._extent is not None:
            start, end = self._extent
            band = QColor(theme.SELECTION)
            band.setAlpha(70)
            rect = (
                QRectF(start, 0, end - start, RULER_SIZE) if horizontal else QRectF(0, start, RULER_SIZE, end - start)
            )
            painter.fillRect(rect, band)
        ink = palette.windowText().color()
        painter.setPen(QPen(ink, 1))
        font = QFont(self.font())
        font.setPointSizeF(_LABEL_POINT_SIZE)
        painter.setFont(font)
        for tick in ruler_ticks(self._start_doc, self._zoom, self._length(), self._unit, self._dpi):
            position = round(tick.screen) + 0.5
            size = _MAJOR_TICK if tick.major else _MINOR_TICK
            if horizontal:
                painter.drawLine(QPointF(position, RULER_SIZE - size), QPointF(position, RULER_SIZE))
                if tick.label is not None:
                    painter.drawText(QPointF(position + 2, _LABEL_POINT_SIZE + 3), tick.label)
            else:
                painter.drawLine(QPointF(RULER_SIZE - size, position), QPointF(RULER_SIZE, position))
                if tick.label is not None:
                    painter.save()
                    painter.translate(_LABEL_POINT_SIZE + 3, position + 2)
                    painter.rotate(-90)
                    painter.drawText(QPointF(-painter.fontMetrics().horizontalAdvance(tick.label) - 2, 0), tick.label)
                    painter.restore()
        if self._pointer is not None:
            painter.setPen(QPen(QColor(theme.ICON_ACTIVE), 1))
            pointer = round(self._pointer) + 0.5
            if horizontal:
                painter.drawLine(QPointF(pointer, 0), QPointF(pointer, RULER_SIZE))
            else:
                painter.drawLine(QPointF(0, pointer), QPointF(RULER_SIZE, pointer))
        painter.setPen(QPen(palette.mid().color(), 1))
        if horizontal:
            painter.drawLine(QPointF(0, RULER_SIZE - 0.5), QPointF(self.width(), RULER_SIZE - 0.5))
        else:
            painter.drawLine(QPointF(RULER_SIZE - 0.5, 0), QPointF(RULER_SIZE - 0.5, self.height()))
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.guide_drag_started.emit(self.orientation)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self.guide_dragged.emit(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.guide_released.emit(event.globalPosition().toPoint())
