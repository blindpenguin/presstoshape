"""Draws the document (and canvas chrome) onto any skia.Canvas whose matrix maps doc units to device px."""

from collections.abc import Iterator

import skia

from presstoshape.geometry import nodes as path_nodes
from presstoshape.models.app_state import Document
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    EllipseShape,
    PathShape,
    RectShape,
    Shape,
    Style,
    TextShape,
    Transform,
)
from presstoshape.render.handles import CONTROL_PX, HANDLE_PX, NODE_PX, Frame, handle_points
from presstoshape.render.overlay import CanvasColors, NodeOverlay, Overlay
from presstoshape.render.paths import PathCache, stroke_paint, to_skia_matrix, to_skia_path
from presstoshape.render.text import text_blob

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
    if shape.transform == IDENTITY_TRANSFORM or isinstance(shape, PathShape):
        _draw_local(canvas, shape, cache)
        return
    canvas.save()
    canvas.concat(to_skia_matrix(shape.transform))
    _draw_local(canvas, shape, cache)
    canvas.restore()


def _draw_local(canvas: skia.Canvas, shape: Shape, cache: PathCache) -> None:
    """Untransformed geometry; cached paths are world space, so paths are drawn as they are."""
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
    matrix: Transform = IDENTITY_TRANSFORM,
    live: tuple[Shape, ...] = (),
) -> None:
    """Draws every visible shape; shapes in `moving` go through `matrix`, or are replaced by `live` (live drag)."""
    replacements = {s.id: s for s in live}
    for shape in visible_shapes(doc):
        if shape.id not in moving:
            draw_shape(canvas, shape, cache)
        elif replacements:
            if shape.id in replacements:
                draw_shape(canvas, replacements[shape.id], cache)
        else:
            canvas.save()
            canvas.concat(to_skia_matrix(matrix))
            draw_shape(canvas, shape, cache)
            canvas.restore()


def _hairline(color: int, dash: float = 0.0, phase: float = 0.0) -> skia.Paint:
    paint = skia.Paint(Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=0, AntiAlias=False)
    if dash:
        paint.setPathEffect(skia.DashPathEffect.Make([dash, dash], phase))
    return paint


def _draw_selection_boxes(
    canvas: skia.Canvas, doc: Document, overlay: Overlay, cache: PathCache, zoom: float, color: int
) -> None:
    dash = _DASH_PX / zoom
    # Alternating dashes stay visible on any fill.
    dashes = (_hairline(color, dash), _hairline(skia.ColorWHITE, dash, dash))
    live = {s.id: s for s in overlay.live}
    matrix = to_skia_matrix(overlay.matrix)
    for shape in visible_shapes(doc):
        if shape.id not in overlay.selection:
            continue
        if shape.id in live:
            bounds = cache.bounds(live[shape.id])
        elif shape.id in overlay.moving:
            bounds = matrix.mapRect(cache.bounds(shape))
        else:
            bounds = cache.bounds(shape)
        for paint in dashes:
            canvas.drawRect(bounds, paint)


def _draw_frame(canvas: skia.Canvas, frame: Frame, zoom: float, color: int) -> None:
    outline = skia.Path()
    outline.addPoly([skia.Point(*p) for p in frame.corners()], True)
    canvas.drawPath(outline, _hairline(color))
    half = HANDLE_PX / 2 / zoom
    fill = skia.Paint(Color=skia.ColorWHITE)
    border = _hairline(color)
    for x, y in handle_points(frame, zoom).values():
        square = skia.Rect.MakeLTRB(x - half, y - half, x + half, y + half)
        canvas.drawRect(square, fill)
        canvas.drawRect(square, border)


def _draw_nodes(canvas: skia.Canvas, overlay: NodeOverlay, zoom: float, color: int) -> None:
    segments = overlay.segments
    white = skia.Paint(Color=skia.ColorWHITE, AntiAlias=True)
    filled = skia.Paint(Color=color, AntiAlias=True)
    border = skia.Paint(Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=0, AntiAlias=True)
    arm = _hairline(color)
    for ref in overlay.controls:
        ax, ay = path_nodes.control_anchor(segments, ref)
        cx, cy = path_nodes.control_point(segments, ref)
        canvas.drawLine(ax, ay, cx, cy, arm)
    radius = CONTROL_PX / 2 / zoom
    for ref in overlay.controls:
        cx, cy = path_nodes.control_point(segments, ref)
        canvas.drawCircle(cx, cy, radius, white)
        canvas.drawCircle(cx, cy, radius, border)
    half = NODE_PX / 2 / zoom
    for info in path_nodes.nodes(segments):
        x, y = info.point
        square = skia.Rect.MakeLTRB(x - half, y - half, x + half, y + half)
        canvas.drawRect(square, filled if info.index in overlay.selected else white)
        canvas.drawRect(square, border)


def draw_overlays(
    canvas: skia.Canvas, doc: Document, overlay: Overlay, cache: PathCache, zoom: float, colors: CanvasColors
) -> None:
    """Selection boxes and handles, rubber band and drawing preview, sized in screen px; never part of export."""
    selection_color = parse_color(colors.selection)
    # A single selection is outlined by its frame alone; per-shape boxes would just repeat it (or, rotated, clash).
    if overlay.selection and (overlay.frame is None or len(overlay.selection) > 1):
        _draw_selection_boxes(canvas, doc, overlay, cache, zoom, selection_color)
    if overlay.frame is not None:
        _draw_frame(canvas, overlay.frame, zoom, selection_color)
    for node_overlay in overlay.nodes:
        _draw_nodes(canvas, node_overlay, zoom, selection_color)
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
