import logging
from collections.abc import Iterable, Iterator
from dataclasses import replace

import skia
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QAbstractScrollArea, QDialog, QInputDialog, QWidget

from presstoshape.editing import containers
from presstoshape.editing.operations import guides, view
from presstoshape.editing.session import Session
from presstoshape.geometry import units
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.models.layout import Guide
from presstoshape.models.shapes import Shape, children_of
from presstoshape.render.guides import draw_grid, draw_guides
from presstoshape.render.overlay import CanvasColors
from presstoshape.render.paths import PathCache
from presstoshape.render.picture import DocumentPicture, EditModeDrawing
from presstoshape.render.scene import draw_background, draw_overlays, parse_color
from presstoshape.render.viewport import Viewport, scene_rect
from presstoshape.tools.base import CursorType, Mods, ToolContext
from presstoshape.tools.registry import Toolbox
from presstoshape.tools.snapper import Snapper
from presstoshape.views import theme
from presstoshape.views.cursors import qt_cursor
from presstoshape.views.guide_dialog import GuideDialog
from presstoshape.views.ruler_view import RULER_SIZE, Ruler
from presstoshape.views.skia_surface import SkiaGLWidget, SkiaRasterWidget, create_surface

_FIT_MARGIN_PX = 40
_WHEEL_ZOOM = 1.15

_COLORS = CanvasColors(
    pasteboard=theme.PASTEBOARD,
    artboard=theme.ARTBOARD,
    artboard_border=theme.ARTBOARD_BORDER,
    preview=theme.PREVIEW_STROKE,
    selection=theme.SELECTION,
    guide=theme.GUIDE,
    grid=theme.GRID,
    snap=theme.SNAP,
    mask_outline=theme.MASK_OUTLINE,
)

_log = logging.getLogger(__name__)


# Arrow keys nudge what the active tool works on; when there is nothing to move they scroll, as before.
_ARROWS = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}


class CanvasView(QAbstractScrollArea):
    """Scroll area whose viewport is a Skia surface; the document is redrawn from state on every frame.

    Scrollbars mirror `Viewport.scroll_x/y`; gestures (selection, drawing) live in CanvasGestures, panning and
    zooming here.
    """

    # Transient gesture text for the status bar (e.g. rotation angle); None when nothing is in progress.
    hint_changed = Signal(object)

    def __init__(self, session: Session, renderer: str = "auto") -> None:
        """`renderer` is the renderer setting ("auto", "gl", "cpu")."""
        super().__init__()
        self._session = session
        self._state: AppState | None = None
        self._cache = PathCache()
        self._picture = DocumentPicture(self._cache)
        self._edit_mode = EditModeDrawing(self._cache)
        self._toolbox = Toolbox(
            ToolContext(session, self._cache, self._repaint, self._ask_text, edit_guide=self._edit_guide)
        )
        self._vp = Viewport()
        self._residual = (0.0, 0.0)
        self._zoom: int | None = None
        self._doc_size: tuple[float, float] | None = None

        self._pan_from = None
        self._hover_pos: QPointF | None = None
        self._cursor_type: CursorType | None = None
        self._hint: str | None = None
        self._zoom_anchor: tuple[float, float] | None = None
        self._viewport_origin: QPoint | None = None
        # Until the user scrolls or zooms, resizes keep the artboard centered. The window manager may resize the
        # window after startup centering (restored maximized state), which would otherwise leave it off-center.
        self._keeps_artboard_centered = False

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._install_surface(create_surface(self._paint, renderer))
        # Rulers sit in the viewport margins; a drag out of one creates a guide.
        self._rulers = {"horizontal": Ruler("horizontal", self), "vertical": Ruler("vertical", self)}
        self._ruler_corner = QWidget(self)
        self._ruler_corner.setAutoFillBackground(True)
        self._rulers_shown: bool | None = None
        self._new_guide: Guide | None = None
        self._new_guide_orientation = "horizontal"
        self._guide_snapper = Snapper.off()
        for ruler in self._rulers.values():
            ruler.guide_drag_started.connect(self._begin_new_guide)
            ruler.guide_dragged.connect(self._drag_new_guide)
            ruler.guide_released.connect(self._release_new_guide)
        self.horizontalScrollBar().valueChanged.connect(lambda v: self._on_scroll(x=v))
        self.verticalScrollBar().valueChanged.connect(lambda v: self._on_scroll(y=v))

    def _install_surface(self, surface: SkiaGLWidget | SkiaRasterWidget) -> None:
        surface.setMouseTracking(True)
        if isinstance(surface, SkiaGLWidget):
            surface.gl_failed.connect(lambda: QTimer.singleShot(0, self._fall_back_to_raster))
        self.setViewport(surface)
        if self._cursor_type is not None:
            surface.setCursor(qt_cursor(self._cursor_type, surface.devicePixelRatioF()))

    def _fall_back_to_raster(self) -> None:
        _log.warning("OpenGL unavailable for Skia; falling back to CPU rendering")
        self._install_surface(SkiaRasterWidget(self._paint))

    def shutdown(self) -> None:
        # Release Skia's GPU resources while the GL context still exists.
        self.viewport().release()

    def viewportEvent(self, event):
        # The scroll area filters its viewport's events; let paint and resize through so the surface widget
        # renders and resizes its framebuffer itself.
        if event.type() == QEvent.Type.Paint:
            return False
        if event.type() == QEvent.Type.Resize:
            super().viewportEvent(event)
            return False
        if event.type() == QEvent.Type.Leave:
            self._hover_pos = None
        return super().viewportEvent(event)

    # --- state -> view ------------------------------------------------------

    def refresh(self, state: AppState) -> None:
        self._state = state
        doc = state.document
        if (doc.width, doc.height) != self._doc_size:
            self._doc_size = (doc.width, doc.height)
            self._vp = replace(self._vp, scene=scene_rect(doc.width, doc.height)).clamped()
        self._toolbox.switch(state.active_tool)
        self._show_rulers(state.view.show_rulers)
        if state.zoom_percent != self._zoom:
            self._apply_zoom(state.zoom_percent)
        self._cache.prune(_nested_ids(shape for layer in doc.layers for shape in layer.shapes))
        self._sync_scrollbars()
        self._repaint()
        # Undo, selection or zoom can change what's under a pointer that hasn't moved.
        self._update_cursor()

    def _apply_zoom(self, zoom: int) -> None:
        """Keeps the doc point under the anchor fixed: the cursor for wheel zoom, else the viewport center."""
        anchor = self._zoom_anchor or (self._vp.width / 2, self._vp.height / 2)
        self._zoom = zoom
        self._keeps_artboard_centered = False
        self._vp, self._residual = self._vp.zoom_at(zoom / 100, anchor, self._residual)
        self._toolbox.context.pixel_size = 100 / zoom

    def _sync_scrollbars(self) -> None:
        min_x, max_x, min_y, max_y = self._vp.scroll_range()
        for bar, lo, hi, page, value in (
            (self.horizontalScrollBar(), min_x, max_x, self._vp.width, self._vp.scroll_x),
            (self.verticalScrollBar(), min_y, max_y, self._vp.height, self._vp.scroll_y),
        ):
            bar.blockSignals(True)
            bar.setRange(round(lo), round(hi))
            bar.setPageStep(max(1, page))
            bar.setValue(round(value))
            bar.blockSignals(False)

    def _on_scroll(self, x: int | None = None, y: int | None = None) -> None:
        self._keeps_artboard_centered = False
        vp = self._vp
        self._vp = replace(vp, scroll_x=vp.scroll_x if x is None else x, scroll_y=vp.scroll_y if y is None else y)
        self._repaint()
        self._update_cursor()

    def _scroll_by(self, dx: float, dy: float) -> None:
        self._keeps_artboard_centered = False
        self._vp = self._vp.scrolled(dx, dy)
        self._sync_scrollbars()
        self._repaint()

    def _repaint(self) -> None:
        self.viewport().update()
        self._update_rulers()
        hint = self._toolbox.active.hint
        if hint != self._hint:
            self._hint = hint
            self.hint_changed.emit(hint)

    def _update_cursor(self) -> None:
        """Cursor for whatever a press would do under the pointer; left alone while panning."""
        if self._pan_from is not None:
            return
        if self._hover_pos is None:
            cursor_type = self._toolbox.active.hover((float("inf"), float("inf")))
        else:
            cursor_type = self._toolbox.active.hover(self._vp.to_doc((self._hover_pos.x(), self._hover_pos.y())))
        if cursor_type is not self._cursor_type:
            self._cursor_type = cursor_type
            self.viewport().setCursor(qt_cursor(cursor_type, self.viewport().devicePixelRatioF()))

    def _paint(self, canvas: skia.Canvas, width: int, height: int, dpr: float) -> None:
        state = self._state
        canvas.clear(parse_color(theme.PASTEBOARD))
        if state is None:
            return
        canvas.setMatrix(self._vp.matrix(dpr))
        overlay = self._toolbox.active.overlay
        if self._new_guide is not None:
            overlay = replace(overlay, guide_preview=self._new_guide, snap=self._guide_snapper.hits)
        chain = containers.edit_chain(state)
        hidden = frozenset({chain[0].id}) if chain else frozenset()
        draw_background(canvas, state.document, _COLORS)
        self._picture.draw(canvas, state.document, overlay.moving, overlay.matrix, overlay.live, hidden)
        self._picture.draw_copies(canvas, overlay.copies, overlay.matrix)
        if chain:
            self._edit_mode.draw(canvas, chain, overlay, self._vp.zoom, _COLORS)
        visible = self._vp.visible_rect()
        # Snapping only looks around what is on screen; before the first layout there is nothing to go by.
        self._toolbox.context.visible_rect = visible if self._vp.width > 0 and self._vp.height > 0 else None
        view = state.view
        if view.show_grid:
            draw_grid(canvas, units.grid_of(state.document), visible, self._vp.zoom, parse_color(theme.GRID))
        if view.show_guides or overlay.guide_preview is not None:
            shown = state.document.guides if view.show_guides else ()
            draw_guides(canvas, shown, visible, parse_color(theme.GUIDE), overlay.guide_preview)
        # Only selected shapes get a box, and selected shapes are always pickable: no need to filter every frame.
        draw_overlays(canvas, containers.active_shapes(state), overlay, self._cache, self._vp.zoom, _COLORS)

    # --- rulers and new guides -------------------------------------------------

    def _show_rulers(self, shown: bool) -> None:
        if shown == self._rulers_shown:
            return
        self._rulers_shown = shown
        margin = RULER_SIZE if shown else 0
        self.setViewportMargins(margin, margin, 0, 0)
        for widget in (*self._rulers.values(), self._ruler_corner):
            widget.setVisible(shown)
        self._place_rulers()

    def _place_rulers(self) -> None:
        if not self._rulers_shown:
            return
        area = self.viewport().geometry()
        self._rulers["horizontal"].setGeometry(area.x(), area.y() - RULER_SIZE, area.width(), RULER_SIZE)
        self._rulers["vertical"].setGeometry(area.x() - RULER_SIZE, area.y(), RULER_SIZE, area.height())
        self._ruler_corner.setGeometry(area.x() - RULER_SIZE, area.y() - RULER_SIZE, RULER_SIZE, RULER_SIZE)
        self._update_rulers()

    def _update_rulers(self) -> None:
        """Ticks for the current scroll and zoom, the pointer, and the extent of the selection frame."""
        state = self._state
        if not self._rulers_shown or state is None:
            return
        zoom = self._vp.zoom
        left, top = self._vp.to_doc((0.0, 0.0))
        pointer = self._hover_pos
        extent_x = extent_y = None
        frame = self._toolbox.active.overlay.frame
        if frame is not None:
            corners = [self._vp.to_screen(frame.point(u, v)) for u, v in ((0, 0), (1, 0), (0, 1), (1, 1))]
            xs, ys = [corner[0] for corner in corners], [corner[1] for corner in corners]
            extent_x, extent_y = (min(xs), max(xs)), (min(ys), max(ys))
        document = state.document
        self._rulers["horizontal"].set_view(
            left, zoom, document.unit, document.dpi, pointer.x() if pointer is not None else None, extent_x
        )
        self._rulers["vertical"].set_view(
            top, zoom, document.unit, document.dpi, pointer.y() if pointer is not None else None, extent_y
        )

    def _begin_new_guide(self, orientation: str) -> None:
        if self._state is None:
            return
        self._guide_snapper = self._toolbox.context.snapper(guides=False)
        self._new_guide = None
        self._new_guide_orientation = orientation

    def _drag_new_guide(self, global_pos: QPoint) -> None:
        local = self.viewport().mapFromGlobal(global_pos)
        x, y = self._vp.to_doc((local.x(), local.y()))
        horizontal = self._new_guide_orientation == "horizontal"
        ctrl = bool(QGuiApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        position = self._guide_snapper.axis(y if horizontal else x, horizontal, ignore=ctrl)
        self._new_guide = Guide(-1, self._new_guide_orientation, position)
        self._hover_pos = QPointF(local)
        self._repaint()

    def _release_new_guide(self, global_pos: QPoint) -> None:
        guide = self._new_guide
        self._new_guide = None
        self._guide_snapper = Snapper.off()
        local = self.viewport().mapFromGlobal(global_pos)
        # Released back over the ruler (or outside the canvas): no guide.
        if guide is not None and self.viewport().rect().contains(local):
            guides.add_guide(self._session, guide.orientation, guide.position)
        self._repaint()

    def _off_canvas(self, event) -> bool:
        """Over a ruler (left of or above the canvas), where a dragged guide is dropped to delete it."""
        pos = event.position()
        return bool(self._rulers_shown) and (pos.x() < 0 or pos.y() < 0)

    def _edit_guide(self, guide_id: int) -> None:
        state = self._state
        guide = next((guide for guide in state.document.guides if guide.id == guide_id), None) if state else None
        if guide is None:
            return
        dialog = GuideDialog(guide, state.document.unit, state.document.dpi, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.deleted:
            guides.delete_guide(self._session, guide_id)
        else:
            guides.move_guide(self._session, guide_id, dialog.position)

    # --- view navigation ----------------------------------------------------

    def center_artboard(self) -> None:
        if self._doc_size is None:
            return
        w, h = self._doc_size
        z = self._vp.zoom
        self._vp = replace(self._vp, scroll_x=w / 2 * z - self._vp.width / 2, scroll_y=h / 2 * z - self._vp.height / 2)
        self._vp = self._vp.clamped()
        self._keeps_artboard_centered = True
        self._sync_scrollbars()
        self._repaint()

    def view_center(self) -> tuple[float, float]:
        """Doc point at the middle of the viewport (stored in .p2s files)."""
        return self._vp.to_doc((self._vp.width / 2, self._vp.height / 2))

    def center_on(self, point: tuple[float, float]) -> None:
        center_x, center_y = self.view_center()
        zoom = self._vp.zoom
        self._scroll_by((point[0] - center_x) * zoom, (point[1] - center_y) * zoom)

    def fit_artboard(self) -> None:
        if self._doc_size is None:
            return
        w, h = self._doc_size
        vw = self.viewport().width() - 2 * _FIT_MARGIN_PX
        vh = self.viewport().height() - 2 * _FIT_MARGIN_PX
        if w > 0 and h > 0 and vw > 0 and vh > 0:
            view.set_zoom(self._session, min(vw / w, vh / h) * 100)
        self.center_artboard()

    def resizeEvent(self, event):
        # Docks opening/closing beside the canvas move the viewport; scroll by the same amount so the
        # drawing stays put on screen instead of sliding with the viewport edge.
        old = self._viewport_origin
        super().resizeEvent(event)
        size = self.viewport().size()
        self._vp = replace(self._vp, width=size.width(), height=size.height()).clamped()
        new = self.viewport().mapTo(self.window(), QPoint(0, 0))
        if old is not None and new != old:
            shift = new - old
            self._vp = self._vp.scrolled(shift.x(), shift.y())
        self._viewport_origin = new
        self._place_rulers()
        if self._keeps_artboard_centered:
            self.center_artboard()
        else:
            self._sync_scrollbars()

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
        pos = event.position()
        self._zoom_anchor = (pos.x(), pos.y())
        view.set_zoom(self._session, (self._zoom or 100) * factor)
        self._zoom_anchor = None

    # --- input -> gestures --------------------------------------------------

    def _doc_pos(self, event) -> tuple[float, float]:
        pos = event.position()
        return self._vp.to_doc((pos.x(), pos.y()))

    @staticmethod
    def _mods(event) -> Mods:
        mods = event.modifiers()
        return Mods(
            shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
            ctrl=bool(mods & Qt.KeyboardModifier.ControlModifier),
            alt=bool(mods & Qt.KeyboardModifier.AltModifier),
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_from = event.position()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._hover_pos = event.position()
            self._toolbox.active.press(self._doc_pos(event), self._mods(event))
            self._repaint()
            self._update_cursor()

    def mouseMoveEvent(self, event):
        if self._pan_from is not None:
            delta = event.position() - self._pan_from
            self._pan_from = event.position()
            self._scroll_by(-round(delta.x()), -round(delta.y()))
            return
        self._hover_pos = event.position()
        self._toolbox.context.pointer_off_canvas = self._off_canvas(event)
        self._toolbox.active.move(self._doc_pos(event), self._mods(event))
        self._update_cursor()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._pan_from is not None:
            self._pan_from = None
            self._cursor_type = None
            self._update_cursor()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._toolbox.context.pointer_off_canvas = self._off_canvas(event)
            self._toolbox.active.release(self._doc_pos(event), self._mods(event))
            self._toolbox.context.pointer_off_canvas = False
            self._repaint()
            self._update_cursor()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._toolbox.active.double_click(self._doc_pos(event), self._mods(event))
        self._repaint()
        self._update_cursor()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._toolbox.active.key("enter"):
            self._repaint()
        elif event.key() in _ARROWS and self._toolbox.active.nudge(*_ARROWS[event.key()], self._mods(event)):
            self._repaint()
        elif event.key() == Qt.Key.Key_Escape:
            self._toolbox.active.escape()
            self._repaint()
            self._update_cursor()
        else:
            super().keyPressEvent(event)

    def _ask_text(self) -> str | None:
        text, ok = QInputDialog.getText(self, _("Add text"), _("Text:"))
        return text if ok else None


def _nested_ids(shapes: Iterable[Shape]) -> Iterator[int]:
    """Ids of the shapes and everything inside them (Composite parts, group children), whose cached geometry
    hit-testing and drawing keep using."""
    for shape in shapes:
        yield shape.id
        yield from _nested_ids(children_of(shape))
