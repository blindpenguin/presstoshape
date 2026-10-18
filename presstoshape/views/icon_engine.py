from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from presstoshape.views import theme


class SvgIconEngine(QIconEngine):
    """Renders the SVG at whatever size/DPR Qt asks for, recoloring Tabler's currentColor per mode/state."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._source = path.read_text()
        self._renderers: dict[str, QSvgRenderer] = {}

    def _renderer(self, mode: QIcon.Mode, state: QIcon.State) -> QSvgRenderer:
        if mode == QIcon.Mode.Disabled:
            color = theme.ICON_DISABLED
        elif state == QIcon.State.On:
            color = theme.ICON_ACTIVE
        else:
            color = theme.ICON_NORMAL
        if color not in self._renderers:
            svg = self._source.replace("currentColor", color).encode()
            self._renderers[color] = QSvgRenderer(QByteArray(svg))
        return self._renderers[color]

    def paint(self, painter, rect, mode, state):
        self._renderer(mode, state).render(painter, QRectF(rect))

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size, mode, state, scale):
        # Default impl ignores `scale`, which would make icons blurry on HiDPI screens.
        pixmap = QPixmap(size * scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, pixmap.rect(), mode, state)
        painter.end()
        pixmap.setDevicePixelRatio(scale)
        return pixmap

    def clone(self):
        return SvgIconEngine(self._path)


def icon(path: Path) -> QIcon:
    return QIcon(SvgIconEngine(path))
