"""Document <-> screen mapping for the canvas, mirroring QGraphicsView's scrollbar model.

Scroll values are in screen px, like scrollbar values: the scaled scene spans [left * zoom, right * zoom] and the
view shows [scroll, scroll + width] of it. A scaled scene smaller than the view is centered instead.
"""

import math
from dataclasses import dataclass, replace

import skia

from veccy.controllers.geometry import Point

SCENE_MARGIN = 4000.0

Rect = tuple[float, float, float, float]


def scene_rect(doc_width: float, doc_height: float) -> Rect:
    m = SCENE_MARGIN
    return (-m, -m, doc_width + 2 * m, doc_height + 2 * m)


def _clamp_px(value: float, lo: float, hi: float) -> float:
    lo_px, hi_px = math.ceil(lo), math.floor(hi)
    if lo_px > hi_px:
        return float(round(lo))
    return float(min(max(round(value), lo_px), hi_px))


@dataclass(frozen=True)
class Viewport:
    zoom: float = 1.0
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    width: int = 0
    height: int = 0
    scene: Rect = (0.0, 0.0, 0.0, 0.0)

    def scroll_range(self) -> tuple[float, float, float, float]:
        x, y, w, h = self.scene
        z = self.zoom
        return (x * z, max(x * z, (x + w) * z - self.width), y * z, max(y * z, (y + h) * z - self.height))

    def clamped(self) -> "Viewport":
        """Scroll clamped to the range and kept whole-pixel, like a scrollbar (half px would blur hairlines)."""
        min_x, max_x, min_y, max_y = self.scroll_range()
        return replace(
            self,
            scroll_x=_clamp_px(self.scroll_x, min_x, max_x),
            scroll_y=_clamp_px(self.scroll_y, min_y, max_y),
        )

    def offset(self) -> Point:
        """Translation t with screen = doc * zoom + t."""
        x, y, w, h = self.scene
        z = self.zoom
        tx = round((self.width - w * z) / 2 - x * z) if w * z <= self.width else -self.scroll_x
        ty = round((self.height - h * z) / 2 - y * z) if h * z <= self.height else -self.scroll_y
        return tx, ty

    def to_screen(self, p: Point) -> Point:
        tx, ty = self.offset()
        return p[0] * self.zoom + tx, p[1] * self.zoom + ty

    def to_doc(self, p: Point) -> Point:
        tx, ty = self.offset()
        return (p[0] - tx) / self.zoom, (p[1] - ty) / self.zoom

    def matrix(self, dpr: float = 1.0) -> skia.Matrix:
        tx, ty = self.offset()
        z = self.zoom * dpr
        return skia.Matrix.MakeAll(z, 0, tx * dpr, 0, z, ty * dpr, 0, 0, 1)

    def scrolled(self, dx: float, dy: float) -> "Viewport":
        return replace(self, scroll_x=self.scroll_x + dx, scroll_y=self.scroll_y + dy).clamped()

    def zoom_at(self, zoom: float, anchor: Point, residual: Point = (0.0, 0.0)) -> tuple["Viewport", Point]:
        """Rescales keeping the doc point under `anchor` (screen px) fixed.

        Scroll values move in whole px like scrollbars, so the sub-pixel remainder is returned and should be
        passed back on the next call; otherwise repeated zoom steps creep.
        """
        doc_point = self.to_doc(anchor)
        zoomed = replace(self, zoom=zoom).clamped()
        sx, sy = zoomed.to_screen(doc_point)
        drift_x = sx - anchor[0] + residual[0]
        drift_y = sy - anchor[1] + residual[1]
        step_x, step_y = round(drift_x), round(drift_y)
        return zoomed.scrolled(step_x, step_y), (drift_x - step_x, drift_y - step_y)
