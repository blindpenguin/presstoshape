"""Guides and the grid on the canvas: drawn as one-pixel lines over the visible area, never exported."""

import math
from collections.abc import Iterable

import skia

from presstoshape.geometry.boxes import Point, Rect
from presstoshape.models.layout import GridSettings, Guide

# Grid lines closer than this on screen are left out, so zooming out never turns the canvas grey.
MIN_GRID_SPACING_PX = 6.0
_MINOR_ALPHA = 0x30
_MAJOR_ALPHA = 0x60


def guide_at(guides: Iterable[Guide], point: Point, tolerance: float) -> Guide | None:
    """The guide closest to `point` within `tolerance` (document units), or None."""
    best: tuple[float, Guide] | None = None
    for guide in guides:
        distance = abs((point[1] if guide.orientation == "horizontal" else point[0]) - guide.position)
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, guide)
    return best[1] if best is not None else None


def _hairline(color: int) -> skia.Paint:
    # Width 0 is one device pixel at every zoom.
    return skia.Paint(Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=0, AntiAlias=False)


def draw_guides(
    canvas: skia.Canvas, guides: Iterable[Guide], visible: Rect, color: int, preview: Guide | None = None
) -> None:
    """Each guide across the visible area; a dragged guide (`preview`) is drawn where it is being dragged."""
    left, top, width, height = visible
    path = skia.Path()
    shown = [guide for guide in guides if preview is None or guide.id != preview.id]
    if preview is not None:
        shown.append(preview)
    for guide in shown:
        if guide.orientation == "horizontal":
            path.moveTo(left, guide.position)
            path.lineTo(left + width, guide.position)
        else:
            path.moveTo(guide.position, top)
            path.lineTo(guide.position, top + height)
    canvas.drawPath(path, _hairline(color))


def draw_grid(canvas: skia.Canvas, grid: GridSettings, visible: Rect, zoom: float, color: int) -> None:
    """Minor and major grid lines over the visible area, from the document origin. Lines too dense for the zoom
    are skipped (minor ones first)."""
    spacing = grid.spacing
    if spacing <= 0:
        return
    major_spacing = spacing * grid.major_every
    show_minor = spacing * zoom >= MIN_GRID_SPACING_PX
    if not show_minor and major_spacing * zoom < MIN_GRID_SPACING_PX:
        return
    left, top, width, height = visible
    right, bottom = left + width, top + height
    minor, major = skia.Path(), skia.Path()
    step = spacing if show_minor else major_spacing
    for index in range(math.floor(left / step), math.ceil(right / step) + 1):
        x = index * step
        is_major = not show_minor or index % grid.major_every == 0
        target = major if is_major else minor
        target.moveTo(x, top)
        target.lineTo(x, bottom)
    for index in range(math.floor(top / step), math.ceil(bottom / step) + 1):
        y = index * step
        is_major = not show_minor or index % grid.major_every == 0
        target = major if is_major else minor
        target.moveTo(left, y)
        target.lineTo(right, y)
    base = color & 0x00FFFFFF
    canvas.drawPath(minor, _hairline(base | (_MINOR_ALPHA << 24)))
    canvas.drawPath(major, _hairline(base | (_MAJOR_ALPHA << 24)))
