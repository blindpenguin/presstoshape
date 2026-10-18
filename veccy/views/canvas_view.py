from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsScene, QGraphicsView, QInputDialog

from veccy.controllers import geometry
from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment, Shape, Style, TextShape
from veccy.views import theme

_SHAPE_ID = 0
_SCENE_MARGIN = 4000.0
_FIT_MARGIN_PX = 40
_WHEEL_ZOOM = 1.15
_PEN_DEDUPE_PX = 3.0

_CURSORS = {
    Tool.SELECT: Qt.CursorShape.ArrowCursor,
    Tool.TEXT: Qt.CursorShape.IBeamCursor,
}


def _qpath(segments: tuple[Segment, ...]) -> QPainterPath:
    path = QPainterPath()
    # SVG's default fill rule is nonzero; Qt defaults to odd-even.
    path.setFillRule(Qt.FillRule.WindingFill)
    for s in segments:
        match s:
            case MoveTo(x, y):
                path.moveTo(x, y)
            case LineTo(x, y):
                path.lineTo(x, y)
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                path.cubicTo(c1x, c1y, c2x, c2y, x, y)
            case Close():
                path.closeSubpath()
    return path


def shape_qpath(shape: Shape) -> QPainterPath:
    if isinstance(shape, TextShape):
        font = QFont("Sans Serif")
        font.setPixelSize(max(1, round(shape.font_size)))
        path = QPainterPath()
        path.addText(QPointF(shape.x, shape.y), font, shape.text)
        return path
    return _qpath(geometry.outline(shape))


def _apply_style(item: QGraphicsPathItem, style: Style) -> None:
    item.setBrush(QBrush(QColor(style.fill)) if style.fill else QBrush(Qt.BrushStyle.NoBrush))
    if style.stroke and style.stroke_width > 0:
        # Flat cap + miter join are SVG's defaults, so the canvas matches the saved file.
        pen = QPen(QColor(style.stroke), style.stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        item.setPen(pen)
    else:
        item.setPen(QPen(Qt.PenStyle.NoPen))


class CanvasView(QGraphicsView):
    """Mirrors the document into a QGraphicsScene and turns mouse gestures into controller calls.

    Scene items are a cache keyed by shape id — the model stays the source of truth. Qt moves items live while
    dragging; on release the offset goes to the controller and the next sync snaps items back to pos (0, 0).
    """

    def __init__(self, controller: AppController) -> None:
        scene = QGraphicsScene()
        super().__init__(scene)
        scene.setParent(self)
        self._controller = controller
        self._state: AppState | None = None
        self._items: dict[int, tuple[Shape, QGraphicsPathItem]] = {}
        self._syncing = False
        self._tool: Tool | None = None
        self._zoom: int | None = None
        self._artboard = QRectF()

        self._drag_start: QPointF | None = None
        self._preview: QGraphicsPathItem | None = None
        self._pen_points: list[QPointF] = []
        self._pan_from: QPointF | None = None
        self._zoom_anchor: QPointF | None = None
        self._scroll_residual = QPointF()

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Anchoring is done by hand in _apply_zoom: Qt's AnchorUnderMouse uses a scene point cached in
        # QGraphicsView.mouseMoveEvent, which goes stale whenever our gesture handlers skip super().
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setMouseTracking(True)
        scene.selectionChanged.connect(self._on_scene_selection)

    def shutdown(self) -> None:
        # Scene teardown deselects items, which would call into the controller mid-destruction.
        self.scene().selectionChanged.disconnect(self._on_scene_selection)

    # --- state -> scene -----------------------------------------------------

    def refresh(self, state: AppState) -> None:
        self._state = state
        doc = state.document
        artboard = QRectF(0, 0, doc.width, doc.height)
        if artboard != self._artboard:
            self._artboard = artboard
            m = _SCENE_MARGIN
            self.scene().setSceneRect(artboard.adjusted(-m, -m, m, m))
            self.resetCachedContent()
        if state.active_tool is not self._tool:
            self._set_tool(state.active_tool)
        if state.zoom_percent != self._zoom:
            self._apply_zoom(state.zoom_percent)
        self._sync_items(state)

    def _apply_zoom(self, zoom: int) -> None:
        """Rescales keeping the scene point under the anchor fixed: the cursor for wheel zoom, else the center."""
        anchor = self._zoom_anchor or QPointF(self.viewport().rect().center())
        scene_point = self.viewportTransform().inverted()[0].map(anchor)
        self._zoom = zoom
        self.setTransform(QTransform.fromScale(zoom / 100, zoom / 100))
        drift = self.viewportTransform().map(scene_point) - anchor + self._scroll_residual
        # Scrollbars are integer px; carry the remainder so repeated zoom steps don't creep.
        step = QPointF(round(drift.x()), round(drift.y()))
        self._scroll_residual = drift - step
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + int(step.x()))
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + int(step.y()))

    def _sync_items(self, state: AppState) -> None:
        self._syncing = True
        live: set[int] = set()
        z = 0
        for layer in state.document.layers:
            if not layer.visible:
                continue
            for shape in layer.shapes:
                live.add(shape.id)
                entry = self._items.get(shape.id)
                if entry is None:
                    item = QGraphicsPathItem()
                    item.setFlags(
                        QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                    )
                    item.setData(_SHAPE_ID, shape.id)
                    self.scene().addItem(item)
                else:
                    item = entry[1]
                if entry is None or entry[0] != shape:
                    item.setPath(shape_qpath(shape))
                    _apply_style(item, shape.style)
                    self._items[shape.id] = (shape, item)
                if not item.pos().isNull():
                    item.setPos(0, 0)
                item.setZValue(z)
                z += 1
                item.setSelected(shape.id in state.selection)
        for shape_id in [i for i in self._items if i not in live]:
            self.scene().removeItem(self._items.pop(shape_id)[1])
        self._syncing = False

    def _on_scene_selection(self) -> None:
        if self._syncing:
            return
        ids = {item.data(_SHAPE_ID) for item in self.scene().selectedItems()}
        self._controller.set_selection({i for i in ids if i is not None})

    def _set_tool(self, tool: Tool) -> None:
        self._cancel_gesture()
        self._tool = tool
        select = tool is Tool.SELECT
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if select else QGraphicsView.DragMode.NoDrag)
        self.viewport().setCursor(_CURSORS.get(tool, Qt.CursorShape.CrossCursor))

    # --- view navigation ----------------------------------------------------

    def center_artboard(self) -> None:
        self.centerOn(self._artboard.center())

    def fit_artboard(self) -> None:
        w, h = self._artboard.width(), self._artboard.height()
        vw = self.viewport().width() - 2 * _FIT_MARGIN_PX
        vh = self.viewport().height() - 2 * _FIT_MARGIN_PX
        if w > 0 and h > 0 and vw > 0 and vh > 0:
            self._controller.set_zoom(min(vw / w, vh / h) * 100)
        self.center_artboard()

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor(theme.PASTEBOARD))
        painter.fillRect(self._artboard, QColor(theme.ARTBOARD))
        painter.setPen(QPen(QColor(theme.ARTBOARD_BORDER), 0))
        painter.drawRect(self._artboard)

    def wheelEvent(self, event):
        # Middle button is the wheel on most mice, so a pan drag emits stray wheel ticks.
        if self._pan_from is not None or event.buttons() & Qt.MouseButton.MiddleButton:
            event.accept()
            return
        dy = event.angleDelta().y()
        # Smooth pixel scrolling (touchpad, libinput middle-button scrolling) pans; wheel notches zoom.
        notched = event.pixelDelta().isNull()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if dy == 0 or not (notched or ctrl):
            super().wheelEvent(event)
            return
        factor = _WHEEL_ZOOM if dy > 0 else 1 / _WHEEL_ZOOM
        self._zoom_anchor = event.position()
        self._controller.set_zoom((self._zoom or 100) * factor)
        self._zoom_anchor = None

    # --- gestures -----------------------------------------------------------

    def _scene_pos(self, event) -> QPointF:
        return self.mapToScene(event.position().toPoint())

    def _new_preview(self, filled: bool) -> QGraphicsPathItem:
        item = QGraphicsPathItem()
        style = self._state.default_style if self._state else Style()
        _apply_style(item, style if filled else Style(fill=None, stroke=style.stroke, stroke_width=style.stroke_width))
        if item.pen().style() == Qt.PenStyle.NoPen:
            item.setPen(QPen(QColor(theme.PREVIEW_STROKE), 0))
        item.setZValue(1e9)
        self.scene().addItem(item)
        return item

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_from = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if self._tool is Tool.SELECT:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = self._scene_pos(event)
        if self._tool in (Tool.RECTANGLE, Tool.ELLIPSE):
            self._drag_start = pos
            self._preview = self._new_preview(filled=True)
        elif self._tool is Tool.PEN:
            if self._preview is None:
                self._preview = self._new_preview(filled=False)
            self._pen_points.append(pos)
            self._preview.setPath(_qpath(geometry.smooth_segments(self._pen_tuples(self._pen_points))))
        elif self._tool is Tool.TEXT:
            text, ok = QInputDialog.getText(self, "Add text", "Text:")
            if ok:
                self._controller.add_text((pos.x(), pos.y()), text)

    def mouseMoveEvent(self, event):
        if self._pan_from is not None:
            delta = event.position() - self._pan_from
            self._pan_from = event.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - round(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
            return
        pos = self._scene_pos(event)
        if self._drag_start is not None and self._preview is not None:
            square = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            x, y, w, h = geometry.box_from_drag(self._point(self._drag_start), self._point(pos), square)
            path = QPainterPath()
            if self._tool is Tool.RECTANGLE:
                path.addRect(QRectF(x, y, w, h))
            else:
                path.addEllipse(QRectF(x, y, w, h))
            self._preview.setPath(path)
        elif self._tool is Tool.PEN and self._pen_points and self._preview is not None:
            points = self._pen_tuples([*self._pen_points, pos])
            self._preview.setPath(_qpath(geometry.smooth_segments(points)))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_from is not None:
            self._pan_from = None
            self.viewport().setCursor(_CURSORS.get(self._tool, Qt.CursorShape.CrossCursor))
            return
        if self._tool is Tool.SELECT:
            super().mouseReleaseEvent(event)
            moved = next((i for i in self.scene().selectedItems() if not i.pos().isNull()), None)
            if moved is not None:
                self._controller.move_selection(moved.pos().x(), moved.pos().y())
            return
        if self._drag_start is not None and event.button() == Qt.MouseButton.LeftButton:
            start, end = self._point(self._drag_start), self._point(self._scene_pos(event))
            square = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._cancel_gesture()
            if self._tool is Tool.RECTANGLE:
                self._controller.add_rectangle(start, end, square)
            else:
                self._controller.add_ellipse(start, end, square)

    def mouseDoubleClickEvent(self, event):
        if self._tool is Tool.PEN:
            self._finish_pen()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if self._tool is Tool.PEN and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish_pen()
        elif event.key() == Qt.Key.Key_Escape:
            if self._preview is not None:
                self._cancel_gesture()
            else:
                self._controller.set_selection(set())
        else:
            super().keyPressEvent(event)

    def _finish_pen(self) -> None:
        points = self._pen_tuples(self._pen_points)
        self._cancel_gesture()
        self._controller.add_path(points)

    def _pen_tuples(self, points: list[QPointF]) -> list[tuple[float, float]]:
        # Double-click also delivers a press, so near-duplicate points (in screen px) are dropped.
        threshold = _PEN_DEDUPE_PX / self.transform().m11()
        out: list[QPointF] = []
        for p in points:
            if not out or (p - out[-1]).manhattanLength() > threshold:
                out.append(p)
        return [self._point(p) for p in out]

    def _cancel_gesture(self) -> None:
        if self._preview is not None:
            self.scene().removeItem(self._preview)
        self._preview = None
        self._drag_start = None
        self._pen_points = []

    @staticmethod
    def _point(p: QPointF) -> tuple[float, float]:
        return p.x(), p.y()
