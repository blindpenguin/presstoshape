"""Draws the document (and canvas chrome) onto any skia.Canvas whose matrix maps doc units to device px."""

from collections.abc import Mapping

import skia

from veccy.models.app_state import Document
from veccy.models.shapes import Shape
from veccy.render.overlay import CanvasColors
from veccy.render.paths import PathCache, stroke_paint


def parse_color(value: str) -> int:
    """`#rgb`, `#rrggbb` or Qt-style `#aarrggbb` -> skia color."""
    digits = value.lstrip("#")
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    if len(digits) == 6:
        digits = "ff" + digits
    return int(digits, 16)


def draw_background(canvas: skia.Canvas, doc: Document, colors: CanvasColors) -> None:
    canvas.drawColor(parse_color(colors.pasteboard))
    artboard = skia.Rect.MakeWH(doc.width, doc.height)
    canvas.drawRect(artboard, skia.Paint(Color=parse_color(colors.artboard)))
    # Width 0 is a 1-device-px hairline at any zoom.
    border = skia.Paint(Color=parse_color(colors.artboard_border), Style=skia.Paint.kStroke_Style, StrokeWidth=0)
    canvas.drawRect(artboard, border)


def draw_shape(canvas: skia.Canvas, shape: Shape, cache: PathCache) -> None:
    style = shape.style
    path = cache.get(shape)
    if style.fill:
        canvas.drawPath(path, skia.Paint(Color=parse_color(style.fill), AntiAlias=True))
    if style.stroke and style.stroke_width > 0:
        paint = stroke_paint(style.stroke_width)
        paint.setColor(parse_color(style.stroke))
        canvas.drawPath(path, paint)


def draw_document(
    canvas: skia.Canvas, doc: Document, cache: PathCache, overrides: Mapping[int, Shape] | None = None
) -> None:
    """Visible layers bottom to top; `overrides` replaces shapes by id (live drag positions)."""
    overrides = overrides or {}
    for layer in doc.layers:
        if not layer.visible:
            continue
        for shape in layer.shapes:
            draw_shape(canvas, overrides.get(shape.id, shape), cache)
