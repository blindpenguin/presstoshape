"""What dissolving a masked group leaves behind; shared by Release and Ungroup."""

from dataclasses import replace

from presstoshape.models.shapes import GroupShape, Shape, content_children, mask_children

# A released clipping path is drawn as a thin outline: unpainted, it would vanish.
RELEASED_CLIP_STROKE = "#18181b"
RELEASED_CLIP_WIDTH = 1.0


def released_children(group: GroupShape) -> list[Shape]:
    """The children of a masked group once the mask is gone, bottom to top: the content, then the mask objects.
    Clipping paths turn into outlines; the mask objects of an opacity mask stay but are hidden."""
    if group.masking is None:
        return list(group.children)
    if group.masking.type == "clip":
        mask = [_outlined(shape) for shape in mask_children(group)]
    else:
        mask = [replace(shape, hidden=True) for shape in mask_children(group)]
    return [*content_children(group), *mask]


def _outlined(shape: Shape) -> Shape:
    if isinstance(shape, GroupShape):
        return shape
    style = replace(
        shape.style,
        fill=None,
        stroke=RELEASED_CLIP_STROKE,
        stroke_width=RELEASED_CLIP_WIDTH,
        opacity=1.0,
        stroke_opacity=1.0,
    )
    return replace(shape, style=style)
