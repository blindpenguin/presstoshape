"""Model shapes as cached Skia paths, rebuilt only when the frozen shape changes."""

from collections.abc import Iterable

import skia

from veccy.controllers import geometry
from veccy.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment, Shape, TextShape
from veccy.render.text import text_path

# SVG's default stroke-miterlimit.
MITER_LIMIT = 4.0


def to_skia_path(segments: tuple[Segment, ...]) -> skia.Path:
    path = skia.Path()
    # SVG's default fill rule is nonzero.
    path.setFillType(skia.PathFillType.kWinding)
    for s in segments:
        match s:
            case MoveTo(x, y):
                path.moveTo(x, y)
            case LineTo(x, y):
                path.lineTo(x, y)
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                path.cubicTo(c1x, c1y, c2x, c2y, x, y)
            case Close():
                path.close()
    return path


def stroke_paint(width: float) -> skia.Paint:
    """SVG stroke defaults: butt cap, miter join, miter limit 4."""
    return skia.Paint(
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=width,
        StrokeCap=skia.Paint.kButt_Cap,
        StrokeJoin=skia.Paint.kMiter_Join,
        StrokeMiter=MITER_LIMIT,
        AntiAlias=True,
    )


def _build(shape: Shape) -> skia.Path:
    if isinstance(shape, TextShape):
        return text_path(shape)
    return to_skia_path(geometry.outline(shape) or ())


class PathCache:
    """Keyed by shape id; an entry is valid while its stored shape equals the current one."""

    def __init__(self) -> None:
        self._paths: dict[int, tuple[Shape, skia.Path]] = {}
        self._strokes: dict[int, tuple[Shape, float, skia.Path]] = {}

    def get(self, shape: Shape) -> skia.Path:
        entry = self._paths.get(shape.id)
        if entry is None or entry[0] != shape:
            entry = (shape, _build(shape))
            self._paths[shape.id] = entry
        return entry[1]

    def stroke_path(self, shape: Shape, min_width: float = 0.0) -> skia.Path:
        """Filled outline of the shape's stroke, at least `min_width` wide (for hit-testing thin strokes)."""
        width = max(shape.style.stroke_width, min_width)
        entry = self._strokes.get(shape.id)
        if entry is None or entry[0] != shape or entry[1] != width:
            outline = skia.Path()
            stroke_paint(width).getFillPath(self.get(shape), outline)
            entry = (shape, width, outline)
            self._strokes[shape.id] = entry
        return entry[2]

    def bounds(self, shape: Shape) -> skia.Rect:
        """Geometry bounds grown by half the stroke width when stroked (like Qt's item boundingRect)."""
        rect = self.get(shape).computeTightBounds()
        style = shape.style
        if style.stroke and style.stroke_width > 0:
            half = style.stroke_width / 2
            rect = rect.makeOutset(half, half)
        return rect

    def prune(self, live_ids: Iterable[int]) -> None:
        live = set(live_ids)
        for cache in (self._paths, self._strokes):
            for shape_id in [i for i in cache if i not in live]:
                del cache[shape_id]
