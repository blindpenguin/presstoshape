from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from presstoshape.geometry.colours import HSV, hsv_to_hex

_STRIP = 14
_GAP = 6
_MARK = 5


class ColourPicker(QWidget):
    """Saturation/value square with a hue strip beside it. Emits `dragged(hsv)` while the user drags and
    `released(hsv)` at the end; `set_hsv` doesn't emit. Hue is 0..360, saturation and value 0..1."""

    dragged = Signal(tuple)
    released = Signal(tuple)

    def __init__(self) -> None:
        super().__init__()
        self._hsv: HSV = (0.0, 0.0, 0.0)
        self._grab: str | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumSize(120, 110)

    def sizeHint(self) -> QSize:
        return QSize(200, 130)

    @property
    def hsv(self) -> HSV:
        return self._hsv

    def set_hsv(self, hsv: HSV) -> None:
        if hsv != self._hsv:
            self._hsv = hsv
            self.update()

    def _square(self) -> QRectF:
        return QRectF(0.5, 0.5, self.width() - _STRIP - _GAP - 1, self.height() - 1)

    def _strip(self) -> QRectF:
        return QRectF(self.width() - _STRIP - 0.5, 0.5, _STRIP, self.height() - 1)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h, s, v = self._hsv
        square, strip = self._square(), self._strip()

        painter.fillRect(square, QColor(hsv_to_hex((h, 1.0, 1.0))))
        whites = QLinearGradient(square.topLeft(), square.topRight())
        whites.setColorAt(0, QColor(255, 255, 255, 255))
        whites.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(square, whites)
        blacks = QLinearGradient(square.topLeft(), square.bottomLeft())
        blacks.setColorAt(0, QColor(0, 0, 0, 0))
        blacks.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(square, blacks)

        hues = QLinearGradient(strip.topLeft(), strip.bottomLeft())
        for step in range(7):
            hues.setColorAt(step / 6, QColor(hsv_to_hex((step * 60.0, 1.0, 1.0))))
        painter.fillRect(strip, hues)

        painter.setPen(QPen(QColor("#52525b"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(square)
        painter.drawRect(strip)

        mark = QPointF(square.left() + s * square.width(), square.top() + (1 - v) * square.height())
        for color, width in (("#000000", 3), ("#ffffff", 1.5)):
            painter.setPen(QPen(QColor(color), width))
            painter.drawEllipse(mark, _MARK, _MARK)
        y = strip.top() + (h % 360) / 360 * strip.height()
        for color, width in (("#000000", 4), ("#ffffff", 2)):
            painter.setPen(QPen(QColor(color), width))
            painter.drawLine(QPointF(strip.left() - 2, y), QPointF(strip.right() + 2, y))
        painter.end()

    def _hsv_at(self, position: QPointF) -> HSV:
        h, s, v = self._hsv
        if self._grab == "hue":
            strip = self._strip()
            fraction = min(1.0, max(0.0, (position.y() - strip.top()) / strip.height()))
            # The bottom of the strip is red again; keep it at 359.9 so the mark stays at the bottom.
            return min(fraction * 360, 359.9), s, v
        square = self._square()
        s = min(1.0, max(0.0, (position.x() - square.left()) / square.width()))
        v = min(1.0, max(0.0, 1 - (position.y() - square.top()) / square.height()))
        return h, s, v

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return
        self._grab = "hue" if event.position().x() >= self._strip().left() - _GAP / 2 else "square"
        self._drag_to(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._grab is not None:
            self._drag_to(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._grab is None or event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_to(event.position())
        self._grab = None
        self.released.emit(self._hsv)

    def _drag_to(self, position: QPointF) -> None:
        hsv = self._hsv_at(position)
        if hsv != self._hsv:
            self._hsv = hsv
            self.update()
            self.dragged.emit(hsv)
