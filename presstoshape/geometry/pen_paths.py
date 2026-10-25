"""Pen nodes (a point with optional bezier handles) and the path segments they make."""

from collections.abc import Sequence
from dataclasses import dataclass

from presstoshape.geometry.boxes import Point
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment


@dataclass(frozen=True)
class PenNode:
    point: Point
    # Absolute doc coordinates; None means the segment on that side arrives or leaves without a handle.
    handle_in: Point | None = None
    handle_out: Point | None = None


def mirrored(anchor: Point, handle: Point) -> Point:
    return 2 * anchor[0] - handle[0], 2 * anchor[1] - handle[1]


def with_drag(node: PenNode, pointer: Point, mirror: bool = True) -> PenNode:
    """`node` with its outgoing handle at `pointer`; the incoming one mirrors it, or stays put."""
    if pointer == node.point:
        return PenNode(node.point, None if mirror else node.handle_in, None)
    handle_in = mirrored(node.point, pointer) if mirror else node.handle_in
    return PenNode(node.point, handle_in, pointer)


def _segment(a: PenNode, b: PenNode) -> Segment:
    if a.handle_out is None and b.handle_in is None:
        return LineTo(*b.point)
    c1 = a.handle_out or a.point
    c2 = b.handle_in or b.point
    return CubicTo(c1[0], c1[1], c2[0], c2[1], b.point[0], b.point[1])


def pen_segments(nodes: Sequence[PenNode], closed: bool = False) -> tuple[Segment, ...]:
    """Straight where neither end has a handle on that side, a cubic otherwise. A closed path ends with Close; a
    curved closing segment ends on the start point first, which geometry.nodes treats as the same node."""
    if not nodes:
        return ()
    segments: list[Segment] = [MoveTo(*nodes[0].point)]
    segments.extend(_segment(a, b) for a, b in zip(nodes, nodes[1:]))
    if closed and len(nodes) > 1:
        closing = _segment(nodes[-1], nodes[0])
        if isinstance(closing, CubicTo):
            segments.append(closing)
        segments.append(Close())
    return tuple(segments)
