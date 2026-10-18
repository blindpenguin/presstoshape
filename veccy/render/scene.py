"""Draws the document (and canvas chrome) onto any skia.Canvas whose matrix maps doc units to device px."""

from collections.abc import Iterator

import skia

from veccy.models.app_state import Document
from veccy.models.shapes import EllipseShape, RectShape, Shape, Style, TextShape
from veccy.render.overlay import CanvasColors, Overlay
from veccy.render.paths import PathCache, stroke_paint, to_skia_path
from veccy.render.text import text_blob

_DASH_PX = 4.0
_RUBBER_BAND_ALPHA = 0x33


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


def _paints(style: Style) -> Iterator[skia.Paint]:
    if style.fill:
        yield skia.Paint(Color=parse_color(style.fill), AntiAlias=True)
    if style.stroke and style.stroke_width > 0:
        paint = stroke_paint(style.stroke_width)
        paint.setColor(parse_color(style.stroke))
        yield paint


def _draw_path(canvas: skia.Canvas, path: skia.Path, style: Style) -> None:
    for paint in _paints(style):
        canvas.drawPath(path, paint)


def draw_shape(canvas: skia.Canvas, shape: Shape, cache: PathCache) -> None:
    # Rects, ovals and text have analytic / glyph-cache GPU fast paths; generic paths are far slower to draw.
    match shape:
        case RectShape(x=x, y=y, width=w, height=h):
            rect = skia.Rect.MakeXYWH(x, y, w, h)
            for paint in _paints(shape.style):
                canvas.drawRect(rect, paint)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            oval = skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)
            for paint in _paints(shape.style):
                canvas.drawOval(oval, paint)
        case TextShape():
            blob = text_blob(shape)
            if blob is not None:
                for paint in _paints(shape.style):
                    canvas.drawTextBlob(blob, shape.x, shape.y, paint)
        case _:
            _draw_path(canvas, cache.get(shape), shape.style)


def visible_shapes(doc: Document) -> Iterator[Shape]:
    """Paint order: visible layers bottom to top."""
    for layer in doc.layers:
        if layer.visible:
            yield from layer.shapes


def draw_document(
    canvas: skia.Canvas,
    doc: Document,
    cache: PathCache,
    moving: frozenset[int] = frozenset(),
    offset: tuple[float, float] = (0.0, 0.0),
) -> None:
    """Draws every visible shape; shapes in `moving` are shifted by `offset` (live drag)."""
    for shape in visible_shapes(doc):
        if shape.id in moving:
            canvas.save()
            canvas.translate(*offset)
            draw_shape(canvas, shape, cache)
            canvas.restore()
        else:
            draw_shape(canvas, shape, cache)


def _hairline(color: int, dash: float = 0.0, phase: float = 0.0) -> skia.Paint:
    paint = skia.Paint(Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=0, AntiAlias=False)
    if dash:
        paint.setPathEffect(skia.DashPathEffect.Make([dash, dash], phase))
    return paint


def draw_overlays(
    canvas: skia.Canvas, doc: Document, overlay: Overlay, cache: PathCache, zoom: float, colors: CanvasColors
) -> None:
    """Selection boxes, rubber band and drawing preview, 1 screen px wide at any zoom; never part of export."""
    selection_color = parse_color(colors.selection)
    if overlay.selection:
        dash = _DASH_PX / zoom
        # Alternating dashes stay visible on any fill.
        dashes = (_hairline(selection_color, dash), _hairline(skia.ColorWHITE, dash, dash))
        for shape in visible_shapes(doc):
            if shape.id in overlay.selection:
                bounds = cache.bounds(shape)
                if shape.id in overlay.moving:
                    bounds = bounds.makeOffset(*overlay.offset)
                for paint in dashes:
                    canvas.drawRect(bounds, paint)
    if overlay.preview is not None:
        segments, style = overlay.preview
        path = to_skia_path(segments)
        _draw_path(canvas, path, style)
        if not style.stroke or style.stroke_width <= 0:
            canvas.drawPath(path, _hairline(parse_color(colors.preview)))
    if overlay.rubber_band is not None:
        rect = skia.Rect.MakeXYWH(*overlay.rubber_band)
        fill = skia.Paint(Color=(selection_color & 0x00FFFFFF) | (_RUBBER_BAND_ALPHA << 24))
        canvas.drawRect(rect, fill)
        canvas.drawRect(rect, _hairline(selection_color))
