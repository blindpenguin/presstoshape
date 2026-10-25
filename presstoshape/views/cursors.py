"""CursorType -> QCursor. Rotate, node-insert and the Pen's are vector cursors drawn from the app's Tabler icons."""

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QCursor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from presstoshape import icons
from presstoshape.tools.base import CursorType

_SIZE_PX = 24
_INK = "#18181b"
_HALO = "#ffffff"

_SHAPES = {
    CursorType.ARROW: Qt.CursorShape.ArrowCursor,
    CursorType.MOVE: Qt.CursorShape.SizeAllCursor,
    CursorType.RESIZE_H: Qt.CursorShape.SizeHorCursor,
    CursorType.RESIZE_V: Qt.CursorShape.SizeVerCursor,
    CursorType.RESIZE_FDIAG: Qt.CursorShape.SizeFDiagCursor,
    CursorType.RESIZE_BDIAG: Qt.CursorShape.SizeBDiagCursor,
    CursorType.CROSS: Qt.CursorShape.CrossCursor,
    CursorType.IBEAM: Qt.CursorShape.IBeamCursor,
    CursorType.NODE: Qt.CursorShape.PointingHandCursor,
    CursorType.DUPLICATE: Qt.CursorShape.DragCopyCursor,
    CursorType.GUIDE_HORIZONTAL: Qt.CursorShape.SplitVCursor,
    CursorType.GUIDE_VERTICAL: Qt.CursorShape.SplitHCursor,
}

_CUSTOM = {
    CursorType.ROTATE: icons.CURSOR_ROTATE,
    CursorType.NODE_INSERT: icons.CURSOR_NODE_INSERT,
    CursorType.PEN_ADD: icons.CURSOR_PEN_ADD,
    CursorType.PEN_CLOSE: icons.CURSOR_PEN_CLOSE,
    CursorType.PEN_CONTINUE: icons.CURSOR_PEN_CONTINUE,
    CursorType.CORNER: icons.CURSOR_CORNER,
}


def qt_cursor(cursor_type: CursorType, dpr: float) -> QCursor:
    if cursor_type in _CUSTOM:
        return _svg_cursor(_CUSTOM[cursor_type], dpr)
    return QCursor(_SHAPES[cursor_type])


@cache
def _svg_cursor(path: Path, dpr: float) -> QCursor:
    source = path.read_text()
    pixmap = QPixmap(round(_SIZE_PX * dpr), round(_SIZE_PX * dpr))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    # A wide white stroke under the dark one keeps the cursor visible on any fill.
    halo = source.replace("currentColor", _HALO).replace('stroke-width="2"', 'stroke-width="4.5"')
    for svg in (halo, source.replace("currentColor", _INK)):
        QSvgRenderer(QByteArray(svg.encode())).render(painter, QRectF(pixmap.rect()))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return QCursor(pixmap, _SIZE_PX // 2, _SIZE_PX // 2)
