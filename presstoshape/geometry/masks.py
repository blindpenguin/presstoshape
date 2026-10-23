"""The area a masked group shows, as one outline (for writing clip paths, where nothing nested is allowed)."""

from collections.abc import Iterable

import pathops

from presstoshape.geometry import booleans
from presstoshape.geometry.transforms import area_outline
from presstoshape.models.shapes import GroupShape, Segment, Shape, content_children, mask_children

Segments = tuple[Segment, ...]


def visible_outline(group: GroupShape) -> Segments:
    """Content of `group` cut by its clip. An opacity mask only fades the content, so it counts in full; text
    has no vector outline here and is left out."""
    try:
        content = _union(_areas(content_children(group)))
        masking = group.masking
        if masking is None or masking.type != "clip" or not content:
            return content
        clip = _union(_areas(mask_children(group)))
        return booleans.combine_parts([(content, "add"), (clip, "subtract" if masking.inverted else "intersect")])
    except pathops.PathOpsError:
        return ()


def _areas(shapes: Iterable[Shape]) -> list[Segments]:
    result: list[Segments] = []
    for shape in shapes:
        if shape.hidden:
            continue
        if isinstance(shape, GroupShape):
            outline = visible_outline(shape)
        else:
            outline = area_outline(shape) or ()
        if outline:
            result.append(outline)
    return result


def _union(areas: list[Segments]) -> Segments:
    return booleans.combine_parts([(area, "add") for area in areas])
