from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from presstoshape.i18n import _
from presstoshape.models.colours import PaintSlot
from presstoshape.models.shapes import LinearGradient, Paint, RadialGradient

_SIZE = 30
_OFFSET = 14
_RING = 7
_BORDER = "#a1a1aa"
_ACTIVE_BORDER = "#60a5fa"


def checkerboard() -> QBrush:
    """Behind see-through colours, so their opacity shows."""
    tile = QPixmap(8, 8)
    tile.fill(QColor("#ffffff"))
    painter = QPainter(tile)
    painter.fillRect(0, 0, 4, 4, QColor("#d4d4d8"))
    painter.fillRect(4, 4, 4, 4, QColor("#d4d4d8"))
    painter.end()
    return QBrush(tile)


def paint_brush(paint: Paint, rect: QRectF, opacity: float = 1.0) -> QBrush | None:
    """How a swatch shows `paint`: the colour, a gradient strip of the stops, None for no paint."""
    if isinstance(paint, str):
        color = QColor(paint)
        color.setAlphaF(opacity)
        return QBrush(color)
    if isinstance(paint, (LinearGradient, RadialGradient)):
        strip = QLinearGradient(rect.topLeft(), rect.topRight())
        for stop in paint.stops:
            color = QColor(stop.color)
            color.setAlphaF(stop.opacity * opacity)
            strip.setColorAt(stop.offset, color)
        return QBrush(strip)
    return None


class PaintPair(QWidget):
    """Fill square and stroke ring, the active one in front, crossed out for no paint and "?" where selected shapes
    differ. Emits `activated(slot)` on a click."""

    activated = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._fill: tuple[Paint, float, bool] = (None, 1.0, False)
        self._stroke: tuple[Paint, float, bool] = (None, 1.0, False)
        self._active: PaintSlot = "fill"
        self.setFixedSize(QSize(_SIZE + _OFFSET + 2, _SIZE + _OFFSET + 2))

    def show_paints(
        self,
        fill: Paint,
        fill_opacity: float,
        fill_mixed: bool,
        stroke: Paint,
        stroke_opacity: float,
        stroke_mixed: bool,
        active: PaintSlot,
    ) -> None:
        values = ((fill, fill_opacity, fill_mixed), (stroke, stroke_opacity, stroke_mixed), active)
        if values != (self._fill, self._stroke, self._active):
            self._fill, self._stroke, self._active = values
            self.setToolTip(_("Fill") if active == "fill" else _("Stroke"))
            self.update()

    def _rect(self, slot: PaintSlot) -> QRectF:
        offset = 1 if slot == "fill" else _OFFSET + 1
        return QRectF(offset + 0.5, offset + 0.5, _SIZE, _SIZE)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        order: tuple[PaintSlot, PaintSlot] = ("stroke", "fill") if self._active == "fill" else ("fill", "stroke")
        for slot in order:
            self._draw(painter, slot)
        painter.end()

    def _draw(self, painter: QPainter, slot: PaintSlot) -> None:
        rect = self._rect(slot)
        paint, opacity, mixed = self._fill if slot == "fill" else self._stroke
        shape = QPainterPath()
        shape.addRoundedRect(rect, 3, 3)
        if slot == "stroke":
            hole = QPainterPath()
            hole.addRect(rect.adjusted(_RING, _RING, -_RING, -_RING))
            shape = shape.subtracted(hole)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(checkerboard())
        painter.drawPath(shape)
        brush = None if mixed else paint_brush(paint, rect, opacity)
        if brush is not None:
            painter.setBrush(brush)
            painter.drawPath(shape)
        elif mixed:
            painter.setBrush(QColor("#71717a"))
            painter.drawPath(shape)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "?")
        else:
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(QPointF(rect.left() + 2, rect.bottom() - 2), QPointF(rect.right() - 2, rect.top() + 2))
        active = slot == self._active
        painter.setPen(QPen(QColor(_ACTIVE_BORDER if active else _BORDER), 2 if active else 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 3, 3)
        if slot == "stroke":
            painter.drawRect(rect.adjusted(_RING, _RING, -_RING, -_RING))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        position = event.position()
        # The one in front wins where they overlap.
        front: PaintSlot = self._active
        back: PaintSlot = "stroke" if front == "fill" else "fill"
        for slot in (front, back):
            if self._rect(slot).contains(position):
                self.activated.emit(slot)
                return
