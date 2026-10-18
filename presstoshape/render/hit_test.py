"""Picking shapes by point and by rectangle, on the same cached geometry the canvas draws."""

from collections.abc import Sequence

import skia

from presstoshape.geometry.boxes import Rect
from presstoshape.models.shapes import CompositeShape, Shape
from presstoshape.render.paths import PathCache


def _area(shape: Shape, cache: PathCache, tolerance: float = 0.0) -> list[skia.Path]:
    """Pickable regions: the fill if painted, the stroke if painted; an unpainted shape falls back to its fill.

    A Composite with an empty result is picked by the bounds of its parts, so it can't get lost.
    """
    if isinstance(shape, CompositeShape) and cache.get(shape).isEmpty():
        box = skia.Path()
        box.addRect(cache.bounds(shape))
        return [box]
    style = shape.style
    stroked = bool(style.stroke) and style.stroke_width > 0
    regions = []
    if style.fill or not stroked:
        regions.append(cache.get(shape))
    if stroked:
        regions.append(cache.stroke_path(shape, 2 * tolerance))
    return regions


def shape_at(shapes: Sequence[Shape], cache: PathCache, point: tuple[float, float], tolerance: float) -> int | None:
    """Top-most of `shapes` (given bottom to top) under `point`; `tolerance` (doc units) widens thin strokes."""
    x, y = point
    for shape in reversed(shapes):
        b = cache.bounds(shape)
        if not (b.fLeft - tolerance <= x <= b.fRight + tolerance and b.fTop - tolerance <= y <= b.fBottom + tolerance):
            continue
        if any(region.contains(x, y) for region in _area(shape, cache, tolerance)):
            return shape.id
    return None


def shapes_in_rect(shapes: Sequence[Shape], cache: PathCache, rect: Rect) -> set[int]:
    """Those of `shapes` whose pickable area intersects `rect` (x, y, w, h in doc units)."""
    band = skia.Rect.MakeXYWH(*rect)
    band.sort()
    band_path = skia.Path()
    band_path.addRect(band)
    hits: set[int] = set()
    for shape in shapes:
        bounds = cache.bounds(shape)
        if not skia.Rect.Intersects(band, bounds):
            continue
        if band.contains(bounds) or any(
            not skia.Op(region, band_path, skia.PathOp.kIntersect_PathOp).isEmpty()
            for region in _area(shape, cache)
        ):
            hits.add(shape.id)
    return hits
