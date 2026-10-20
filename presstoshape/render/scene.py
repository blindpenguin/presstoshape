"""Draws the document (and canvas chrome) onto any skia.Canvas whose matrix maps doc units to device px."""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import replace

import skia

from presstoshape.geometry import nodes as path_nodes
from presstoshape.geometry import transforms
from presstoshape.geometry.snapping import SnapHit, SnapTarget
from presstoshape.i18n import pgettext
from presstoshape.models.app_state import Document
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    CompositeShape,
    ContainerShape,
    EllipseShape,
    GroupShape,
    PathShape,
    RectShape,
    Shape,
    Style,
    TextShape,
    Transform,
    children_of,
)
from presstoshape.render.handles import CONTROL_PX, HANDLE_PX, NODE_PX, Frame, handle_points
from presstoshape.render.overlay import CanvasColors, NodeOverlay, Overlay
from presstoshape.render.paths import PathCache, stroke_paint, to_skia_matrix, to_skia_path
from presstoshape.render.text import anchor_offset, text_blob, typeface

_DASH_PX = 4.0
_RUBBER_BAND_ALPHA = 0x33
# Edit mode: how strongly everything around the edited Composite is dimmed, and how its parts are outlined.
_DIM_ALPHA = 0x99
_BASE_PART_PX = 2.0
_MODE_DASHES_PX: dict[str, tuple[float, ...]] = {
    "add": (),
    "subtract": (6.0, 4.0),
    "intersect": (1.5, 3.0),
    "exclude": (6.0, 3.0, 1.5, 3.0),
}
_EVERYWHERE = skia.Rect.MakeLTRB(-1e7, -1e7, 1e7, 1e7)
# Snap feedback, in screen px.
_SNAP_DASH_PX = 4.0
_SNAP_CROSS_PX = 4.0
_SNAP_LABEL_PX = 11.0
_SNAP_LABEL_OFFSET_PX = 8.0


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


def _filled(style: Style) -> bool:
    return bool(style.fill)


def _stroked(style: Style) -> bool:
    return bool(style.stroke) and style.stroke_width > 0


def _paints(style: Style, opacity: float = 1.0) -> Iterator[skia.Paint]:
    """Fill then stroke paint, each with its paint opacity times `opacity`."""
    if _filled(style):
        paint = skia.Paint(Color=parse_color(style.fill), AntiAlias=True)
        if style.fill_opacity * opacity < 1:
            paint.setAlphaf(style.fill_opacity * opacity)
        yield paint
    if _stroked(style):
        paint = stroke_paint(style)
        paint.setColor(parse_color(style.stroke))
        if style.stroke_opacity * opacity < 1:
            paint.setAlphaf(style.stroke_opacity * opacity)
        yield paint


def _draw_path(canvas: skia.Canvas, path: skia.Path, style: Style) -> None:
    for paint in _paints(style, style.opacity):
        canvas.drawPath(path, paint)


def draw_shape(canvas: skia.Canvas, shape: Shape, cache: PathCache) -> None:
    if shape.hidden:
        return
    if isinstance(shape, GroupShape):
        _draw_group(canvas, shape, cache)
        return
    style = shape.style
    if style.opacity <= 0:
        return
    # With fill and stroke, object opacity must apply to both flattened together (where the stroke covers the
    # fill, the fill mustn't show through), which needs a layer; with one paint its alpha does the same.
    layered = style.opacity < 1 and _filled(style) and _stroked(style)
    if layered:
        canvas.saveLayerAlpha(cache.bounds(shape), round(style.opacity * 255))
    if shape.transform == IDENTITY_TRANSFORM or isinstance(shape, PathShape):
        _draw_local(canvas, shape, cache, 1.0 if layered else style.opacity)
    else:
        canvas.save()
        canvas.concat(to_skia_matrix(shape.transform))
        _draw_local(canvas, shape, cache, 1.0 if layered else style.opacity)
        canvas.restore()
    if layered:
        canvas.restore()


def _draw_group(canvas: skia.Canvas, group: GroupShape, cache: PathCache) -> None:
    """Children in order; below full opacity they are flattened in a layer first, as SVG renders group opacity."""
    if group.opacity <= 0:
        return
    layered = group.opacity < 1
    if layered:
        canvas.saveLayerAlpha(cache.bounds(group), round(group.opacity * 255))
    for child in group.children:
        draw_shape(canvas, child, cache)
    if layered:
        canvas.restore()


def _draw_local(canvas: skia.Canvas, shape: Shape, cache: PathCache, opacity: float) -> None:
    """Untransformed geometry; cached paths are world space, so paths are drawn as they are."""
    # Rects, ovals and text have analytic / glyph-cache GPU fast paths; generic paths are far slower to draw.
    match shape:
        case RectShape(x=x, y=y, width=w, height=h, rx=rx, ry=ry):
            rect = skia.Rect.MakeXYWH(x, y, w, h)
            # SVG clamps each radius on its own; skia would shrink both together.
            rx, ry = min(rx, w / 2), min(ry, h / 2)
            rounded = skia.RRect.MakeRectXY(rect, rx, ry) if rx > 0 and ry > 0 else None
            for paint in _paints(shape.style, opacity):
                if rounded is None:
                    canvas.drawRect(rect, paint)
                else:
                    canvas.drawRRect(rounded, paint)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            oval = skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)
            for paint in _paints(shape.style, opacity):
                canvas.drawOval(oval, paint)
        case TextShape():
            blob = text_blob(shape)
            if blob is not None:
                x = shape.x + anchor_offset(shape)
                for paint in _paints(shape.style, opacity):
                    canvas.drawTextBlob(blob, x, shape.y, paint)
        case _:
            for paint in _paints(shape.style, opacity):
                canvas.drawPath(cache.get(shape), paint)


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
    canvas: skia.Canvas, shapes: Iterable[Shape], overlay: Overlay, cache: PathCache, zoom: float, color: int
) -> None:
    dash = _DASH_PX / zoom
    # Alternating dashes stay visible on any fill.
    dashes = (_hairline(color, dash), _hairline(skia.ColorWHITE, dash, dash))
    live = {s.id: s for s in overlay.live}
    matrix = to_skia_matrix(overlay.matrix)
    for shape in shapes:
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


def _live(shape: Shape, overlay: Overlay) -> Shape:
    """`shape` where the running gesture shows it: its live replacement, or moved by the overlay matrix."""
    live = {replacement.id: replacement for replacement in overlay.live}
    if shape.id in live:
        return live[shape.id]
    if shape.id in overlay.moving:
        try:
            return transforms.transform_shape(shape, overlay.matrix)
        except ValueError:
            return shape
    return shape


def live_container(container: ContainerShape, overlay: Overlay) -> ContainerShape:
    """The entered Composite or group with the shapes a gesture is dragging in their preview position."""
    children = [_live(child, overlay) for child in children_of(container)]
    if isinstance(container, GroupShape):
        return replace(container, children=tuple(children))
    return replace(container, parts=tuple(children))


def _with_child(parent: ContainerShape, child: Shape) -> ContainerShape:
    children = tuple(child if shape.id == child.id else shape for shape in children_of(parent))
    if isinstance(parent, GroupShape):
        return replace(parent, children=children)
    return replace(parent, parts=children)


def edit_mode_outer(chain: Sequence[ContainerShape], overlay: Overlay) -> Shape:
    """The top-level shape around the entered one, as drawn dimmed behind it.

    Inside a group its contents are left out (they are drawn undimmed on top), so this stays the same object
    value while shapes inside are dragged. Inside a Composite the outer result depends on the live parts, so
    they are included."""
    innermost = chain[-1]
    if isinstance(innermost, GroupShape):
        updated: Shape = replace(innermost, children=())
    else:
        updated = live_container(innermost, overlay)
    for parent in reversed(chain[:-1]):
        updated = _with_child(parent, updated)
    return updated


def draw_composite_parts(canvas: skia.Canvas, composite: CompositeShape, zoom: float, colors: CanvasColors) -> None:
    """The entered Composite's live result and its parts' outlines styled by mode (Add solid, Subtract dashed,
    Intersect dotted, Exclude dash-dot; the base thicker)."""
    _draw_path(canvas, to_skia_path(transforms.outline(composite) or ()), composite.style)
    selection_color = parse_color(colors.selection)
    for index, (part, mode) in enumerate(zip(composite.parts, composite.modes)):
        if part.hidden:
            continue
        part_outline = transforms.outline(part)
        if not part_outline:
            continue
        paint = skia.Paint(Color=selection_color, Style=skia.Paint.kStroke_Style, AntiAlias=True)
        if index == 0:
            paint.setStrokeWidth(_BASE_PART_PX / zoom)
        else:
            paint.setStrokeWidth(0)
            dashes = _MODE_DASHES_PX[mode]
            if dashes:
                paint.setPathEffect(skia.DashPathEffect.Make([length / zoom for length in dashes], 0))
        canvas.drawPath(to_skia_path(part_outline), paint)


def draw_dim(canvas: skia.Canvas, colors: CanvasColors) -> None:
    dim = parse_color(colors.pasteboard) & 0x00FFFFFF | (_DIM_ALPHA << 24)
    canvas.drawRect(_EVERYWHERE, skia.Paint(Color=dim))


def draw_edit_mode(
    canvas: skia.Canvas,
    chain: Sequence[ContainerShape],
    overlay: Overlay,
    zoom: float,
    colors: CanvasColors,
    cache: PathCache | None = None,
) -> None:
    """Draws the entered shapes (outer to inner; the top-level one is hidden from the document picture): the
    surroundings dimmed, then the innermost Composite's live result and part outlines, or the innermost group's
    shapes undimmed. Unrecorded; the canvas uses picture.EditModeDrawing, which caches the same drawing."""
    cache = cache or PathCache()
    draw_shape(canvas, edit_mode_outer(chain, overlay), cache)
    draw_dim(canvas, colors)
    container = live_container(chain[-1], overlay)
    if isinstance(container, CompositeShape):
        draw_composite_parts(canvas, container, zoom, colors)
    else:
        for child in container.children:
            draw_shape(canvas, child, cache)


def draw_overlays(
    canvas: skia.Canvas,
    shapes: Iterable[Shape],
    overlay: Overlay,
    cache: PathCache,
    zoom: float,
    colors: CanvasColors,
) -> None:
    """Selection boxes and handles, rubber band and drawing preview, sized in screen px; never part of export.

    `shapes` are the ones the user can pick right now (their selected ones get a box).
    """
    selection_color = parse_color(colors.selection)
    # A single selection is outlined by its frame alone; per-shape boxes would just repeat it (or, rotated, clash).
    if overlay.selection and (overlay.frame is None or len(overlay.selection) > 1):
        _draw_selection_boxes(canvas, shapes, overlay, cache, zoom, selection_color)
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
    if overlay.snap:
        _draw_snap_feedback(canvas, overlay.snap, zoom, parse_color(colors.snap))


def snap_label(target: SnapTarget) -> str:
    labels = {
        "grid": pgettext("snap", "Grid"),
        "guide": pgettext("snap", "Guide"),
        "artboard": pgettext("snap", "Artboard"),
        "edge": pgettext("snap", "Edge"),
        "centre": pgettext("snap", "Centre"),
        "node": pgettext("snap", "Node"),
    }
    return labels[target]


def _draw_snap_feedback(canvas: skia.Canvas, hits: Sequence[SnapHit], zoom: float, color: int) -> None:
    """Dashed lines to what was lined up with, a cross at snapped points, and one small label."""
    line_paint = _hairline(color, _SNAP_DASH_PX / zoom)
    line_paint.setAntiAlias(True)
    for hit in hits:
        if hit.line is not None:
            (x0, y0), (x1, y1) = hit.line
            canvas.drawLine(x0, y0, x1, y1, line_paint)
        if hit.axis == "point":
            arm = _SNAP_CROSS_PX / zoom
            x, y = hit.at
            cross = skia.Paint(Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=1.5 / zoom, AntiAlias=True)
            canvas.drawLine(x - arm, y - arm, x + arm, y + arm, cross)
            canvas.drawLine(x - arm, y + arm, x + arm, y - arm, cross)
    first = hits[0]
    font = skia.Font(typeface(), _SNAP_LABEL_PX / zoom)
    text = snap_label(first.target)
    pad = 3 / zoom
    x, y = first.at[0] + _SNAP_LABEL_OFFSET_PX / zoom, first.at[1] - _SNAP_LABEL_OFFSET_PX / zoom
    width = font.measureText(text)
    background = skia.Rect.MakeLTRB(x - pad, y - font.getSize() - pad / 2, x + width + pad, y + pad)
    canvas.drawRoundRect(background, pad, pad, skia.Paint(Color=color, AntiAlias=True))
    canvas.drawSimpleText(text, x, y - pad / 2, font, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True))
