"""Structural path edits on segment tuples: node types, lines and curves, break and join, open and close, reverse,
combine and split. Pure functions; the path and node operations share them.

Every edit works on subpaths in anchor/edge form (`Sub`): `edges[e]` runs from `anchors[e]` to the next anchor,
wrapping round on closed subpaths. Only `to_subs` / `from_subs` know about MoveTo, Close and the alias end node of
a closed subpath. Edits return `Edited`, whose `index_map` takes surviving node indices of the input to the
output, so callers can keep the node selection, and whose `focus` holds the nodes the edit made or joined.
"""

import math
from dataclasses import dataclass, replace
from typing import Literal

from presstoshape.geometry.boxes import Point
from presstoshape.geometry.nodes import Anchor, Edge, Segments, Topology, anchors_and_edges, rebuild

NodeKind = Literal["corner", "smooth", "symmetric"]

_TINY = 1e-9


@dataclass(frozen=True)
class Sub:
    anchors: tuple[Anchor, ...]
    edges: tuple[Edge, ...]
    closed: bool

    def edge_ends(self, e: int) -> tuple[int, int]:
        return e, (e + 1) % len(self.anchors)


@dataclass(frozen=True)
class Edited:
    segments: Segments
    index_map: dict[int, int]
    focus: frozenset[int] = frozenset()


def to_subs(segments: Segments) -> list[Sub]:
    subs = []
    for sp in Topology(segments).subpaths:
        anchors, edges = anchors_and_edges(segments, sp)
        subs.append(Sub(tuple(anchors), tuple(edges), sp.closed))
    return subs


def from_subs(subs: list[Sub]) -> Edited:
    out: list = []
    index_map: dict[int, int] = {}
    focus: set[int] = set()
    for sub in subs:
        if not sub.anchors:
            continue
        start = len(out)
        for k, anchor in enumerate(sub.anchors):
            if anchor.source is not None:
                index_map[anchor.source] = start + k
            if anchor.mark:
                focus.add(start + k)
        n = len(sub.anchors)
        out.extend(rebuild(list(sub.anchors), list(sub.edges), list(range(n)), sub.closed))
    return Edited(tuple(out), index_map, frozenset(focus))


def _unit(v: Point) -> Point | None:
    length = math.hypot(*v)
    return None if length < _TINY else (v[0] / length, v[1] / length)


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _third(a: Point, b: Point) -> Point:
    """The point a third of the way from `a` to `b`."""
    return a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3


def _sides(sub: Sub, k: int) -> tuple[int | None, int | None]:
    """The edges arriving at and leaving anchor `k`; None at the ends of an open subpath."""
    n = len(sub.anchors)
    if n < 2:
        return None, None
    before = (k - 1) % n if sub.closed or k > 0 else None
    after = k if sub.closed or k < n - 1 else None
    return before, after


def _smooth_handles(sub: Sub, k: int, symmetric: bool) -> tuple[Point, Point] | None:
    """New (incoming, outgoing) handles for a smooth node, or None when the node can't be smoothed."""
    before, after = _sides(sub, k)
    if before is None or after is None:
        return None
    p = sub.anchors[k].point
    prev = sub.anchors[before].point
    nxt = sub.anchors[sub.edge_ends(after)[1]].point
    edge_in, edge_out = sub.edges[before], sub.edges[after]
    handle_in = edge_in[1] if edge_in is not None else None
    handle_out = edge_out[0] if edge_out is not None else None
    u_in = _unit(_sub(handle_in, p)) if handle_in is not None else None
    u_out = _unit(_sub(handle_out, p)) if handle_out is not None else None
    direction = None
    if u_in is not None and u_out is not None:
        direction = _unit((u_out[0] - u_in[0], u_out[1] - u_in[1]))
    if direction is None:
        direction = _unit(_sub(nxt, prev))
    if direction is None:
        return None
    len_in = _dist(handle_in, p) if u_in is not None else _dist(prev, p) / 3
    len_out = _dist(handle_out, p) if u_out is not None else _dist(nxt, p) / 3
    if symmetric:
        len_in = len_out = (len_in + len_out) / 2
    dx, dy = direction
    return (p[0] - dx * len_in, p[1] - dy * len_in), (p[0] + dx * len_out, p[1] + dy * len_out)


def _retracted(sub: Sub, chosen: set[int]) -> Sub:
    """Corner as in Illustrator: the chosen nodes' handles go back into the node; a segment left with no handle
    sticking out on either end becomes a line."""
    anchors = list(sub.anchors)
    corners = set()
    for k, anchor in enumerate(sub.anchors):
        if anchor.source in chosen:
            anchors[k] = replace(anchor, corner=True)
            corners.add(k)
    edges = list(sub.edges)
    for e, edge in enumerate(sub.edges):
        a, b = sub.edge_ends(e)
        if edge is None or (a not in corners and b not in corners):
            continue
        pa, pb = sub.anchors[a].point, sub.anchors[b].point
        c1 = pa if a in corners else edge[0]
        c2 = pb if b in corners else edge[1]
        edges[e] = None if _dist(c1, pa) < _TINY and _dist(c2, pb) < _TINY else (c1, c2)
    return Sub(tuple(anchors), tuple(edges), sub.closed)


def _set_types(sub: Sub, indices: set[int], kind: NodeKind) -> Sub:
    if kind == "corner":
        return _retracted(sub, indices)
    anchors = list(sub.anchors)
    # Computed from the unchanged subpath, so neighbouring selected nodes don't see each other's new handles.
    handles: dict[int, tuple[Point, Point]] = {}
    for k, anchor in enumerate(sub.anchors):
        if anchor.source not in indices:
            continue
        anchors[k] = replace(anchor, corner=False)
        new = _smooth_handles(sub, k, kind == "symmetric")
        if new is not None:
            handles[k] = new
    edges = list(sub.edges)
    for e, edge in enumerate(sub.edges):
        a, b = sub.edge_ends(e)
        if a not in handles and b not in handles:
            continue
        pa, pb = sub.anchors[a].point, sub.anchors[b].point
        c1, c2 = edge if edge is not None else (_third(pa, pb), _third(pb, pa))
        if a in handles:
            c1 = handles[a][1]
        if b in handles:
            c2 = handles[b][0]
        edges[e] = (c1, c2)
    return Sub(tuple(anchors), tuple(edges), sub.closed)


def set_node_type(segments: Segments, indices, kind: NodeKind) -> Edited:
    """Corner pulls the nodes' handles back into them (as Illustrator does); segments left without handles become
    lines. Smooth lines both handles up through the node (along their average direction, or the direction between
    the neighbours when a handle is missing); symmetric also evens their lengths. Line segments next to a smoothed
    node become curves; end nodes of open subpaths only lose the corner flag."""
    chosen = set(indices)
    return from_subs([_set_types(sub, chosen, kind) for sub in to_subs(segments)])


def _between(sub: Sub, chosen: set[int]):
    """Edges whose both ends are chosen nodes."""
    for e in range(len(sub.edges)):
        a, b = sub.edge_ends(e)
        if sub.anchors[a].source in chosen and sub.anchors[b].source in chosen:
            yield e


def make_lines(segments: Segments, indices) -> Edited:
    chosen = set(indices)
    subs = []
    for sub in to_subs(segments):
        edges = list(sub.edges)
        for e in _between(sub, chosen):
            edges[e] = None
        subs.append(Sub(sub.anchors, tuple(edges), sub.closed))
    return from_subs(subs)


def make_curves(segments: Segments, indices) -> Edited:
    """Lines between chosen nodes become cubics with handles at a third and two thirds (same shape)."""
    chosen = set(indices)
    subs = []
    for sub in to_subs(segments):
        edges = list(sub.edges)
        for e in _between(sub, chosen):
            if edges[e] is None:
                a, b = sub.edge_ends(e)
                pa, pb = sub.anchors[a].point, sub.anchors[b].point
                edges[e] = (_third(pa, pb), _third(pb, pa))
        subs.append(Sub(sub.anchors, tuple(edges), sub.closed))
    return from_subs(subs)


def end_nodes(segments: Segments) -> set[int]:
    """First and last nodes of open subpaths."""
    out: set[int] = set()
    for sub in to_subs(segments):
        if not sub.closed and sub.anchors:
            out.update(a.source for a in (sub.anchors[0], sub.anchors[-1]) if a.source is not None)
    return out


def has_edge_between(segments: Segments, indices) -> bool:
    """Whether any segment joins two of the given nodes."""
    chosen = set(indices)
    return any(next(_between(sub, chosen), None) is not None for sub in to_subs(segments))


def has_line_between(segments: Segments, indices) -> bool:
    chosen = set(indices)
    return any(sub.edges[e] is None for sub in to_subs(segments) for e in _between(sub, chosen))


def has_curve_between(segments: Segments, indices) -> bool:
    chosen = set(indices)
    return any(sub.edges[e] is not None for sub in to_subs(segments) for e in _between(sub, chosen))


# --- break, delete segment, open and close ---------------------------------------


def _rotated_open(sub: Sub, k: int) -> Sub:
    """A closed subpath opened at anchor `k`: it starts there and ends on a marked copy of it."""
    n = len(sub.anchors)
    order = [(k + i) % n for i in range(n)]
    start = replace(sub.anchors[k], mark=True)
    anchors = (start, *(sub.anchors[i] for i in order[1:]), replace(start, source=None))
    return Sub(anchors, tuple(sub.edges[i] for i in order), False)


def _pieces(sub: Sub, cuts: list[int]) -> list[Sub]:
    """An open subpath cut at interior anchor positions: each cut node ends one piece and, as a marked copy,
    starts the next."""
    last = len(sub.anchors) - 1
    inner = sorted({k for k in cuts if 0 < k < last})
    if not inner:
        return [sub]
    bounds = [0, *inner, last]
    pieces = []
    for begin, end in zip(bounds, bounds[1:]):
        anchors = list(sub.anchors[begin : end + 1])
        if begin in inner:
            anchors[0] = replace(anchors[0], source=None, mark=True)
        if end in inner:
            anchors[-1] = replace(anchors[-1], mark=True)
        pieces.append(Sub(tuple(anchors), sub.edges[begin:end], False))
    return pieces


def _positions(sub: Sub, chosen: set[int]) -> list[int]:
    return [k for k, anchor in enumerate(sub.anchors) if anchor.source in chosen]


def _break(sub: Sub, chosen: set[int]) -> list[Sub]:
    positions = _positions(sub, chosen)
    if not positions:
        return [sub]
    if sub.closed:
        first = positions[0]
        n = len(sub.anchors)
        sub = _rotated_open(sub, first)
        positions = [(k - first) % n for k in positions[1:]]
    return _pieces(sub, positions)


def break_at(segments: Segments, indices) -> Edited:
    """Splits each chosen node into two end nodes: a closed subpath opens there, an open one splits into two
    subpaths of the same path. End nodes stay as they are."""
    chosen = set(indices)
    return from_subs([piece for sub in to_subs(segments) for piece in _break(sub, chosen)])


def delete_segments(segments: Segments, indices) -> Edited | None:
    """Removes every segment between two chosen nodes. Subpaths left with one node go; None when nothing is left."""
    chosen = set(indices)
    subs = []
    for sub in to_subs(segments):
        cut = list(_between(sub, chosen))
        if not cut:
            subs.append(sub)
            continue
        n = len(sub.anchors)
        if sub.closed:
            # Open after the first removed segment; the others are then counted from there.
            first = cut[0]
            sub = _rotated_open(sub, (first + 1) % n)
            sub = Sub(sub.anchors[:-1], sub.edges[:-1], False)
            cut = [(e - first - 1) % n for e in cut[1:]]
        begin = 0
        for e in sorted(cut):
            subs.append(Sub(sub.anchors[begin : e + 1], sub.edges[begin:e], False))
            begin = e + 1
        subs.append(Sub(sub.anchors[begin:], sub.edges[begin:], False))
    kept = [sub for sub in subs if len(sub.anchors) > 1]
    if not kept:
        return None
    return from_subs(kept)


def _affected(sub: Sub, chosen: set[int] | None) -> bool:
    return chosen is None or any(anchor.source in chosen for anchor in sub.anchors)


def close_subpaths(segments: Segments, indices=None) -> Edited:
    """Closes open subpaths (all, or those with a chosen node) with a straight segment; ends lying on each other
    merge into one node instead."""
    chosen = None if indices is None else set(indices)
    subs = []
    for sub in to_subs(segments):
        if sub.closed or len(sub.anchors) < 2 or not _affected(sub, chosen):
            subs.append(sub)
        elif len(sub.anchors) > 2 and _dist(sub.anchors[0].point, sub.anchors[-1].point) < _TINY:
            subs.append(Sub(sub.anchors[:-1], sub.edges, True))
        else:
            subs.append(Sub(sub.anchors, (*sub.edges, None), True))
    return from_subs(subs)


def open_subpaths(segments: Segments) -> Edited:
    """Opens every closed subpath at its first node."""
    firsts = {sub.anchors[0].source for sub in to_subs(segments) if sub.closed and sub.anchors}
    return break_at(segments, firsts)


# --- reverse --------------------------------------------------------------------


def _swapped(edge: Edge) -> Edge:
    return None if edge is None else (edge[1], edge[0])


def _reversed(sub: Sub) -> Sub:
    n = len(sub.anchors)
    if not sub.closed:
        return Sub(sub.anchors[::-1], tuple(_swapped(e) for e in sub.edges[::-1]), False)
    anchors = (sub.anchors[0], *sub.anchors[:0:-1])
    return Sub(anchors, tuple(_swapped(sub.edges[(-j - 1) % n]) for j in range(n)), True)


def reverse(segments: Segments, indices=None) -> Edited:
    """Reverses the direction of every subpath (or those with a chosen node) without changing the drawn shape;
    closed subpaths keep their start node."""
    chosen = None if indices is None else set(indices)
    return from_subs([_reversed(sub) if _affected(sub, chosen) else sub for sub in to_subs(segments)])


# --- join -----------------------------------------------------------------------


def _locate(subs: list[Sub], index: int) -> tuple[int, int] | None:
    """(subpath, anchor position) of node `index` when it is an end of an open subpath."""
    for i, sub in enumerate(subs):
        if sub.closed or len(sub.anchors) < 2:
            continue
        if sub.anchors[0].source == index:
            return i, 0
        if sub.anchors[-1].source == index:
            return i, len(sub.anchors) - 1
    return None


def _moved_edge(edge: Edge, start: Point | None, end: Point | None) -> Edge:
    """`edge` with the control at its start shifted by `start` and the one at its end by `end`."""
    if edge is None:
        return None
    c1, c2 = edge
    if start is not None:
        c1 = (c1[0] + start[0], c1[1] + start[1])
    if end is not None:
        c2 = (c2[0] + end[0], c2[1] + end[1])
    return c1, c2


def _merged(a: Anchor, b: Anchor) -> tuple[Anchor, Point, Point]:
    """The node replacing `a` and `b` at their midpoint, and how far each of them moved."""
    mid = ((a.point[0] + b.point[0]) / 2, (a.point[1] + b.point[1]) / 2)
    node = Anchor(mid, a.corner or b.corner, a.source, mark=True)
    return node, _sub(mid, a.point), _sub(mid, b.point)


def join_ends(segments: Segments, a: int, b: int, with_segment: bool) -> Edited | None:
    """Joins two end nodes of open subpaths: by a straight segment, or by merging them at their midpoint (keeping
    the handle arriving at one and the one leaving the other). Two ends of one subpath close it; ends of two
    subpaths make one, reversing one of them where needed. None when `a` and `b` aren't two such end nodes."""
    subs = to_subs(segments)
    where_a, where_b = _locate(subs, a), _locate(subs, b)
    if where_a is None or where_b is None or a == b:
        return None
    (ia, ka), (ib, kb) = where_a, where_b
    if ia == ib:
        sub = subs[ia]
        if ka != 0:
            sub = _reversed(sub)
        # Now `a` starts the subpath and `b` ends it.
        first, last = replace(sub.anchors[0], mark=True), replace(sub.anchors[-1], mark=True)
        if with_segment:
            subs[ia] = Sub((first, *sub.anchors[1:-1], last), (*sub.edges, None), True)
        elif len(sub.anchors) < 3:
            return None
        else:
            node, shift_first, shift_last = _merged(first, last)
            edges = list(sub.edges)
            edges[0] = _moved_edge(edges[0], shift_first, None)
            edges[-1] = _moved_edge(edges[-1], None, shift_last)
            subs[ia] = Sub((node, *sub.anchors[1:-1]), tuple(edges), True)
        return from_subs(subs)
    sub_a, sub_b = subs[ia], subs[ib]
    if ka == 0:
        sub_a = _reversed(sub_a)
    if kb != 0:
        sub_b = _reversed(sub_b)
    # Now `sub_a` ends at `a` and `sub_b` starts at `b`.
    end_a, start_b = replace(sub_a.anchors[-1], mark=True), replace(sub_b.anchors[0], mark=True)
    if with_segment:
        joined = Sub(
            (*sub_a.anchors[:-1], end_a, start_b, *sub_b.anchors[1:]), (*sub_a.edges, None, *sub_b.edges), False
        )
    else:
        node, shift_a, shift_b = _merged(end_a, start_b)
        edges_a = (*sub_a.edges[:-1], _moved_edge(sub_a.edges[-1], None, shift_a))
        edges_b = (_moved_edge(sub_b.edges[0], shift_b, None), *sub_b.edges[1:])
        joined = Sub((*sub_a.anchors[:-1], node, *sub_b.anchors[1:]), (*edges_a, *edges_b), False)
    subs[ia] = joined
    del subs[ib]
    return from_subs(subs)


# --- combine and split ------------------------------------------------------------


def combine(paths: list[Segments]) -> Segments:
    """All subpaths in one segment tuple; node indices of later paths shift by the lengths before them."""
    return tuple(segment for segments in paths for segment in segments)


def split(segments: Segments) -> list[Segments]:
    """One segment tuple per subpath that has a drawn segment."""
    return [from_subs([sub]).segments for sub in to_subs(segments) if len(sub.anchors) > 1]
