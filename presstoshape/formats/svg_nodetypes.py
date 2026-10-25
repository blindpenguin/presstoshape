"""Corner nodes in SVG as Inkscape's `sodipodi:nodetypes`: one letter per node and subpath (`c` corner, `s`
smooth, `z` symmetric), a closed subpath's first node written again at its end. Inkscape reads that repeated
letter, not the first one, as the start node's type, so we do too. Only the corner flag is kept: smooth and
symmetric already follow from the handles."""

import math
from dataclasses import replace

from presstoshape.geometry import nodes
from presstoshape.geometry.nodes import NodeInfo
from presstoshape.models.shapes import Segment

Segments = tuple[Segment, ...]

_SAME_LENGTH = 1e-6


def _letter(segments: Segments, info: NodeInfo) -> str:
    if segments[info.index].corner or not info.smooth:
        return "c"
    a, b = (nodes.control_point(segments, ref) for ref in info.controls)
    la = math.hypot(a[0] - info.point[0], a[1] - info.point[1])
    lb = math.hypot(b[0] - info.point[0], b[1] - info.point[1])
    return "z" if abs(la - lb) <= _SAME_LENGTH * max(la, lb, 1.0) else "s"


def _groups(segments: Segments) -> list[tuple[list[NodeInfo], bool]]:
    """The nodes of each subpath, in order, and whether it is closed."""
    topo = nodes.Topology(segments)
    infos = nodes.nodes(segments)
    return [([info for info in infos if sp.start <= info.index < sp.end], sp.closed) for sp in topo.subpaths]


def node_types(segments: Segments) -> str | None:
    """The attribute value, or None when no node is a corner (then nothing is lost by leaving it out)."""
    if not any(getattr(segment, "corner", False) for segment in segments):
        return None
    letters = []
    for infos, closed in _groups(segments):
        group = [_letter(segments, info) for info in infos]
        letters.extend(group)
        if closed and group:
            letters.append(group[0])
    return "".join(letters)


def with_node_types(segments: Segments, value: str | None) -> Segments:
    """Marks the nodes typed `c` whose handles line up as corners. A value that doesn't fit the nodes (written for
    other path data) is ignored."""
    if not value:
        return segments
    letters = value.strip()
    groups = _groups(segments)
    if len(letters) != sum(len(infos) + (1 if closed and infos else 0) for infos, closed in groups):
        return segments
    out = list(segments)
    position = 0
    for infos, closed in groups:
        typed = list(zip(infos, letters[position : position + len(infos)]))
        position += len(infos)
        if closed and infos:
            typed[0] = (infos[0], letters[position])
            position += 1
        for info, letter in typed:
            if letter == "c" and info.smooth:
                out[info.index] = replace(out[info.index], corner=True)
    return tuple(out)
