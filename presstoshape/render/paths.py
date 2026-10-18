"""Model shapes as cached Skia paths, rebuilt only when the frozen shape changes."""

from collections.abc import Iterable

import skia

from presstoshape.geometry import transforms
from presstoshape.geometry.segments import quad_to_cubic
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    Close,
    CompositeShape,
    CubicTo,
    LineTo,
    MoveTo,
    Segment,
    Shape,
    TextShape,
    Transform,
)
from presstoshape.render.text import text_path

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


def from_skia_path(path: skia.Path) -> tuple[Segment, ...]:
    """Inverse of `to_skia_path`; quads and conics become cubics."""
    out: list[Segment] = []
    it = skia.Path.RawIter(path)
    while True:
        verb, pts = it.next()
        match verb:
            case skia.Path.kDone_Verb:
                return tuple(out)
            case skia.Path.kMove_Verb:
                out.append(MoveTo(pts[0].x(), pts[0].y()))
            case skia.Path.kLine_Verb:
                out.append(LineTo(pts[1].x(), pts[1].y()))
            case skia.Path.kQuad_Verb:
                out.append(quad_to_cubic(*((p.x(), p.y()) for p in pts)))
            case skia.Path.kConic_Verb:
                quads = skia.Path.ConvertConicToQuads(pts[0], pts[1], pts[2], it.conicWeight(), 2)
                for i in range(0, len(quads) - 2, 2):
                    out.append(quad_to_cubic(*((p.x(), p.y()) for p in quads[i : i + 3])))
            case skia.Path.kCubic_Verb:
                out.append(CubicTo(*(v for p in pts[1:] for v in (p.x(), p.y()))))
            case skia.Path.kClose_Verb:
                out.append(Close())


def to_skia_matrix(m: Transform) -> skia.Matrix:
    a, b, c, d, e, f = m
    return skia.Matrix.MakeAll(a, c, e, b, d, f, 0, 0, 1)


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
    """World-space geometry: the shape's transform is applied."""
    if isinstance(shape, TextShape):
        path = text_path(shape)
        if shape.transform != IDENTITY_TRANSFORM:
            path.transform(to_skia_matrix(shape.transform))
        return path
    return to_skia_path(transforms.outline(shape) or ())


def _bounds(shape: Shape, path: skia.Path) -> skia.Rect:
    rect = path.computeTightBounds()
    style = shape.style
    if style.stroke and style.stroke_width > 0:
        half = style.stroke_width / 2
        rect = rect.makeOutset(half, half)
    return rect


class PathCache:
    """Keyed by shape id; an entry is valid while its stored shape equals the current one."""

    def __init__(self) -> None:
        self._paths: dict[int, tuple[Shape, skia.Path, skia.Rect]] = {}
        self._strokes: dict[int, tuple[Shape, float, skia.Path]] = {}

    def _entry(self, shape: Shape) -> tuple[Shape, skia.Path, skia.Rect]:
        entry = self._paths.get(shape.id)
        # Identity first: unchanged shapes are the same object, and equality on nested dataclasses is slow.
        if entry is None or (entry[0] is not shape and entry[0] != shape):
            path = _build(shape)
            bounds = _bounds(shape, path)
            if isinstance(shape, CompositeShape) and path.isEmpty():
                bounds = self._union(self.bounds(part) for part in shape.parts)
            entry = (shape, path, bounds)
            self._paths[shape.id] = entry
        return entry

    @staticmethod
    def _union(rects) -> skia.Rect:
        result = skia.Rect.MakeEmpty()
        for rect in rects:
            result.join(rect)
        return result

    def get(self, shape: Shape) -> skia.Path:
        return self._entry(shape)[1]

    def stroke_path(self, shape: Shape, min_width: float = 0.0) -> skia.Path:
        """Filled outline of the shape's stroke, at least `min_width` wide (for hit-testing thin strokes)."""
        width = max(shape.style.stroke_width, min_width)
        entry = self._strokes.get(shape.id)
        if entry is None or (entry[0] is not shape and entry[0] != shape) or entry[1] != width:
            outline = skia.Path()
            stroke_paint(width).getFillPath(self.get(shape), outline)
            entry = (shape, width, outline)
            self._strokes[shape.id] = entry
        return entry[2]

    def bounds(self, shape: Shape) -> skia.Rect:
        """Geometry bounds grown by half the stroke width when stroked (like Qt's item boundingRect)."""
        return self._entry(shape)[2]

    def geometry_bounds(self, shape: Shape) -> skia.Rect:
        """Tight bounds of the transformed geometry, without stroke. An empty Composite uses its parts' bounds,
        so it can still be found, selected and framed."""
        path = self.get(shape)
        if isinstance(shape, CompositeShape) and path.isEmpty():
            return self._union(self.geometry_bounds(part) for part in shape.parts)
        return path.computeTightBounds()

    def prune(self, live_ids: Iterable[int]) -> None:
        live = set(live_ids)
        for cache in (self._paths, self._strokes):
            for shape_id in [i for i in cache if i not in live]:
                del cache[shape_id]
