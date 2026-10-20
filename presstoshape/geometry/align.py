"""Aligning and distributing boxes: how far each one has to move. Boxes are (x, y, width, height)."""

from collections.abc import Sequence
from typing import Literal

from presstoshape.geometry.boxes import Point, Rect

AlignEdge = Literal["left", "hcenter", "right", "top", "vcenter", "bottom"]
DistributeMode = Literal["gaps_x", "gaps_y", "centers_x", "centers_y"]


def union(boxes: Sequence[Rect]) -> Rect:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return left, top, right - left, bottom - top


def _anchor(box: Rect, edge: AlignEdge) -> float:
    """The coordinate of `box` that `edge` lines up."""
    x, y, width, height = box
    match edge:
        case "left":
            return x
        case "hcenter":
            return x + width / 2
        case "right":
            return x + width
        case "top":
            return y
        case "vcenter":
            return y + height / 2
        case "bottom":
            return y + height


def align_offsets(boxes: Sequence[Rect], edge: AlignEdge, reference: Rect) -> list[Point]:
    """Moves that bring each box's edge (or centre) onto the reference box's."""
    target = _anchor(reference, edge)
    horizontal = edge in ("left", "hcenter", "right")
    offsets = []
    for box in boxes:
        delta = target - _anchor(box, edge)
        offsets.append((delta, 0.0) if horizontal else (0.0, delta))
    return offsets


def distribute_offsets(boxes: Sequence[Rect], mode: DistributeMode) -> list[Point]:
    """Moves that space the boxes evenly along one axis, keeping their order and the outermost two in place.

    Gap modes make the space between neighbours equal (negative when they don't fit, so they overlap evenly);
    centre modes make the distance between centres equal. Fewer than three boxes don't move."""
    count = len(boxes)
    if count < 3:
        return [(0.0, 0.0)] * count
    axis = 0 if mode.endswith("_x") else 1
    starts = [box[axis] for box in boxes]
    sizes = [box[axis + 2] for box in boxes]
    if mode.startswith("centers"):
        centres = [start + size / 2 for start, size in zip(starts, sizes)]
        order = sorted(range(count), key=lambda index: centres[index])
        first, last = centres[order[0]], centres[order[-1]]
        step = (last - first) / (count - 1)
        targets = {index: first + rank * step - sizes[index] / 2 for rank, index in enumerate(order)}
    else:
        order = sorted(range(count), key=lambda index: starts[index])
        first = starts[order[0]]
        end = max(start + size for start, size in zip(starts, sizes))
        gap = (end - first - sum(sizes)) / (count - 1)
        targets = {}
        position = first
        for index in order:
            targets[index] = position
            position += sizes[index] + gap
    offsets = []
    for index in range(count):
        delta = targets[index] - starts[index]
        offsets.append((delta, 0.0) if axis == 0 else (0.0, delta))
    return offsets
