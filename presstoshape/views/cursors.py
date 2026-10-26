"""CursorType -> QCursor. Rotate, node-insert, corner, eyedropper and the Pen's are vector cursors: a pointer arrow (the hotspot)
with the action's Tabler icon as a badge."""

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QCursor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from presstoshape import icons
from presstoshape.tools.base import CursorType

# Custom cursors are a pointer arrow, whose tip is the exact point a click hits, with the action's icon as a badge
# below and right of it. Sizes in logical px.
_SIZE_PX = 32
_BADGE = QRectF(13, 13, 18, 18)
_INK = "#18181b"
_HALO = "#ffffff"
# A classic pointer with its tip at the hotspot.
_ARROW = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<path d="M 1.5 1.5 L 1.5 19 L 6 14.6 L 9.2 21.8 L 12 20.6 L 8.9 13.6 L 15 13.6 Z" '
    'fill="{fill}" stroke="{stroke}" stroke-width="1.5" stroke-linejoin="round"/></svg>'
)
_HOTSPOT = (2, 2)

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
    CursorType.EYEDROPPER: icons.CURSOR_EYEDROPPER,
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
    pixmap.setDevicePixelRatio(dpr)
    painter = QPainter(pixmap)
    full = QRectF(0, 0, _SIZE_PX, _SIZE_PX)
    QSvgRenderer(QByteArray(_ARROW.format(fill=_INK, stroke=_HALO).encode())).render(painter, full)
    # A wide white stroke under the dark one keeps the badge visible on any fill.
    halo = source.replace("currentColor", _HALO).replace('stroke-width="2"', 'stroke-width="5"')
    for svg in (halo, source.replace("currentColor", _INK)):
        QSvgRenderer(QByteArray(svg.encode())).render(painter, _BADGE)
    painter.end()
    return QCursor(pixmap, *_HOTSPOT)
