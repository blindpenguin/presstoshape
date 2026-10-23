"""Geometry and filters behind clipping and opacity masks; `scene._draw_group` does the drawing."""

from typing import TYPE_CHECKING

import skia

from presstoshape.models.shapes import GroupShape, Shape, content_children, mask_children

if TYPE_CHECKING:
    from presstoshape.render.paths import PathCache

_LUMINANCE = (0.2125, 0.7154, 0.0721)


def shape_area(shape: Shape, cache: "PathCache") -> skia.Path:
    """What a shape covers when it is part of a clip: its fill geometry, never its stroke or paint. A group
    covers what its content shows."""
    if isinstance(shape, GroupShape):
        return _group_area(shape, cache)
    return cache.get(shape)


def _group_area(group: GroupShape, cache: "PathCache") -> skia.Path:
    area = _union(shape_area(child, cache) for child in content_children(group) if not child.hidden)
    if group.masking is not None and group.masking.type == "clip":
        clip = cache.clip(group)
        area = _combine(area, clip, skia.kDifference_PathOp if group.masking.inverted else skia.kIntersect_PathOp)
    return area


def build_clip(group: GroupShape, cache: "PathCache") -> skia.Path:
    """Union of the mask objects' areas, not yet inverted (drawing inverts with the clip operation)."""
    return _union(shape_area(child, cache) for child in mask_children(group) if not child.hidden)


def _union(paths) -> skia.Path:
    result = skia.Path()
    for path in paths:
        result = _combine(result, path, skia.kUnion_PathOp) if not result.isEmpty() else skia.Path(path)
    return result


def _combine(first: skia.Path, second: skia.Path, operation: int) -> skia.Path:
    combined = skia.Op(first, second, operation)
    if combined is not None:
        return combined
    # Degenerate geometry that pathops refuses: the first path alone still beats failing the frame.
    return skia.Path(first)


def mask_filter(mask_type: str, inverted: bool) -> skia.ColorFilter | None:
    """Turns the mask layer into the alpha the content keeps. A luminance layer is drawn over black, so its
    colours are opaque and the luminance of the colour is the mask value; an alpha layer is its own value."""
    if mask_type == "alpha":
        if not inverted:
            return None
        row = [0.0, 0.0, 0.0, -1.0, 1.0]
    else:
        red, green, blue = _LUMINANCE
        row = [-red, -green, -blue, 0.0, 1.0] if inverted else [red, green, blue, 0.0, 0.0]
    return skia.ColorFilters.Matrix([0.0] * 15 + row)
