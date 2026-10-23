"""Qt-free logic behind the Layers panel's object tree: row types and labels, where an object sits, and the
states it gets from the layer and containers around it."""

from dataclasses import dataclass
from typing import Literal

from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GroupShape,
    ImageShape,
    Masking,
    PathShape,
    RectShape,
    Shape,
    TextShape,
    children_of,
)

ObjectType = Literal["rect", "ellipse", "path", "text", "group", "composite", "clip", "mask", "image", "reference"]
ChildRole = Literal["mask", "content"]

_LABEL_LENGTH = 30


def object_type(shape: Shape) -> ObjectType:
    match shape:
        case RectShape():
            return "rect"
        case EllipseShape():
            return "ellipse"
        case PathShape():
            return "path"
        case TextShape():
            return "text"
        case GroupShape(masking=None):
            return "group"
        case GroupShape(masking=Masking(type="clip")):
            return "clip"
        case GroupShape():
            return "mask"
        case CompositeShape():
            return "composite"
        case ImageShape(reference=True):
            return "reference"
        case ImageShape():
            return "image"


def child_role(parent: Shape, child_id: int) -> ChildRole | None:
    """Which side of a masked group a child is on; None for the children of anything else."""
    if not isinstance(parent, GroupShape) or parent.masking is None:
        return None
    return "mask" if parent.masking.is_mask(child_id) else "content"


def object_label(shape: Shape, role: ChildRole | None = None) -> str:
    """The type's name, or for text its first line, shortened; a mask object of a masked group says so."""
    label = _type_label(shape)
    if isinstance(shape, ImageShape) and shape.reference:
        label = _("{object} (reference)").format(object=label)
    return _("{object} (mask)").format(object=label) if role == "mask" else label


def _type_label(shape: Shape) -> str:
    match shape:
        case TextShape(text=text):
            line = text.strip().split("\n", 1)[0].strip()
            if not line:
                return _("Text")
            return line if len(line) <= _LABEL_LENGTH else line[: _LABEL_LENGTH - 1].rstrip() + "…"
        case RectShape():
            return _("Rectangle")
        case EllipseShape():
            return _("Ellipse")
        case PathShape():
            return _("Path")
        case GroupShape(masking=None):
            return _("Group")
        case GroupShape(masking=Masking(type="clip")):
            return _("Clipping Mask")
        case GroupShape():
            return _("Opacity Mask")
        case CompositeShape():
            return _("Composite")
        case ImageShape():
            return _("Image")


@dataclass(frozen=True)
class Location:
    layer_index: int
    # Ids of the groups and Composites around the shape, outer to inner.
    containers: tuple[int, ...]


def locate(state: AppState, shape_id: int) -> Location | None:
    for index, layer in enumerate(state.document.layers):
        pending: list[tuple[Shape, tuple[int, ...]]] = [(shape, ()) for shape in layer.shapes]
        while pending:
            shape, around = pending.pop()
            if shape.id == shape_id:
                return Location(index, around)
            pending.extend((child, (*around, shape.id)) for child in children_of(shape))
    return None


def inherited_flags(state: AppState, location: Location) -> tuple[bool, bool]:
    """(hidden, locked) as the object gets them from its layer and the containers around it."""
    layer = state.document.layers[location.layer_index]
    hidden, locked = not layer.visible, layer.locked
    shapes = layer.shapes
    for container_id in location.containers:
        container = next(shape for shape in shapes if shape.id == container_id)
        hidden, locked = hidden or container.hidden, locked or container.locked
        shapes = children_of(container)
    return hidden, locked
