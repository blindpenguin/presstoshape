"""Picking shapes by point and by rectangle, on the same cached geometry the canvas draws."""

from collections.abc import Sequence

import skia

from presstoshape.geometry.boxes import Rect
from presstoshape.models.shapes import CompositeShape, GroupShape, ImageShape, Shape, content_children
from presstoshape.render.paths import PathCache


def _regions(shape: Shape, cache: PathCache, tolerance: float = 0.0) -> list[skia.Path]:
    """Pickable regions of a shape; a group's are its content's, cut by its clip: mask objects are not pickable."""
    if isinstance(shape, ImageShape) and shape.reference:
        return []
    if isinstance(shape, GroupShape):
        regions = [
            region
            for child in content_children(shape)
            if not child.hidden
            for region in _regions(child, cache, tolerance)
        ]
        if shape.masking is not None and shape.masking.type == "clip":
            operation = skia.PathOp.kDifference_PathOp if shape.masking.inverted else skia.PathOp.kIntersect_PathOp
            regions = [skia.Op(region, cache.clip(shape), operation) or region for region in regions]
        return regions
    return _area(shape, cache, tolerance)


def _contains(shape: Shape, cache: PathCache, x: float, y: float, tolerance: float) -> bool:
    if isinstance(shape, ImageShape) and shape.reference:
        return False
    b = cache.bounds(shape)
    if not (b.fLeft - tolerance <= x <= b.fRight + tolerance and b.fTop - tolerance <= y <= b.fBottom + tolerance):
        return False
    if isinstance(shape, GroupShape):
        if shape.masking is not None and shape.masking.type == "clip":
            if cache.clip(shape).contains(x, y) == shape.masking.inverted:
                return False
        return any(_contains(child, cache, x, y, tolerance) for child in content_children(shape) if not child.hidden)
    return any(region.contains(x, y) for region in _area(shape, cache, tolerance))


def _area(shape: Shape, cache: PathCache, tolerance: float = 0.0) -> list[skia.Path]:
    """Pickable regions: the fill if painted, the stroke if painted; an unpainted shape falls back to its fill.

    A Composite with an empty result is picked by the bounds of its parts, so it can't get lost.
    """
    if isinstance(shape, CompositeShape) and cache.get(shape).isEmpty():
        box = skia.Path()
        box.addRect(cache.bounds(shape))
        return [box]
    if isinstance(shape, ImageShape):
        return [cache.get(shape)]
    style = shape.style
    stroked = bool(style.stroke) and style.stroke_width > 0
    regions = []
    if style.fill or not stroked:
        regions.append(cache.get(shape))
    if stroked:
        regions.append(cache.stroke_path(shape, 2 * tolerance))
    return regions


def shape_at(shapes: Sequence[Shape], cache: PathCache, point: tuple[float, float], tolerance: float) -> int | None:
    """Top-most of `shapes` (given bottom to top) under `point`; `tolerance` (doc units) widens thin strokes.
    Hidden and locked shapes are passed over."""
    x, y = point
    for shape in reversed(shapes):
        if not shape.hidden and not shape.locked and _contains(shape, cache, x, y, tolerance):
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
        if isinstance(shape, ImageShape) and shape.reference:
            continue
        bounds = cache.bounds(shape)
        if not skia.Rect.Intersects(band, bounds):
            continue
        if band.contains(bounds) or any(
            not skia.Op(region, band_path, skia.PathOp.kIntersect_PathOp).isEmpty() for region in _regions(shape, cache)
        ):
            hits.add(shape.id)
    return hits
