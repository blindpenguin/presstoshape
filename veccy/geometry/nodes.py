"""Node-level path editing on segment tuples. Pure functions; the node editing operations and the Node tool share them.

A node is addressed by the index of the segment that ends at it (MoveTo, LineTo or CubicTo). In a closed subpath
whose last segment ends back on its MoveTo point, that last endpoint is an alias of the MoveTo node: it isn't
listed and moves with it. A control point is `(segment_index, 1 | 2)`: c1 belongs to the node before the
segment, c2 to the node the segment ends at.
"""

import math
from dataclasses import dataclass, replace

from veccy.geometry.boxes import Point
from veccy.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment

ControlRef = tuple[int, int]
Segments = tuple[Segment, ...]

_SAME_POINT = 1e-9
_SMOOTH_DEG = 1.0
_SAMPLES = 16


@dataclass(frozen=True)
class NodeInfo:
    index: int
    point: Point
    controls: tuple[ControlRef, ...]
    smooth: bool


@dataclass(frozen=True)
class _Subpath:
    start: int
    # Exclusive; a trailing Close is inside.
    end: int
    closed: bool
    alias: int | None


def _end(s: Segment) -> Point:
    return s.x, s.y


def _is_drawn(s: Segment) -> bool:
    return isinstance(s, (LineTo, CubicTo))


def _subpaths(segments: Segments) -> list[_Subpath]:
    out: list[_Subpath] = []
    i, n = 0, len(segments)
    while i < n:
        if not isinstance(segments[i], MoveTo):
            i += 1
            continue
        j = i + 1
        while j < n and _is_drawn(segments[j]):
            j += 1
        closed = j < n and isinstance(segments[j], Close)
        last = j - 1
        alias = None
        if closed and last > i and _close(_end(segments[last]), _end(segments[i])):
            alias = last
        out.append(_Subpath(i, j + 1 if closed else j, closed, alias))
        i = j + 1 if closed else j
    return out


def _close(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= _SAME_POINT and abs(a[1] - b[1]) <= _SAME_POINT


class _Topology:
    """Which node owns which control, and node aliases, for one segment tuple."""

    def __init__(self, segments: Segments) -> None:
        self.segments = segments
        self.subpaths = _subpaths(segments)
        self.alias_of: dict[int, int] = {}
        self.owner_of: dict[int, int] = {}
        self.subpath_of: dict[int, _Subpath] = {}
        for sp in self.subpaths:
            for i in range(sp.start, sp.end):
                self.subpath_of[i] = sp
            if sp.alias is not None:
                self.alias_of[sp.start] = sp.alias
                self.owner_of[sp.alias] = sp.start

    def node_indices(self) -> list[int]:
        return [
            i
            for sp in self.subpaths
            for i in range(sp.start, sp.end)
            if not isinstance(self.segments[i], Close) and i not in self.owner_of
        ]

    def is_node(self, i: int) -> bool:
        return 0 <= i < len(self.segments) and not isinstance(self.segments[i], Close) and i not in self.owner_of

    def incoming(self, node: int) -> ControlRef | None:
        seg = self.alias_of.get(node, node)
        return (seg, 2) if isinstance(self.segments[seg], CubicTo) else None

    def outgoing(self, node: int) -> ControlRef | None:
        nxt = node + 1
        if nxt < len(self.segments) and isinstance(self.segments[nxt], CubicTo):
            return nxt, 1
        return None

    def controls(self, node: int) -> tuple[ControlRef, ...]:
        return tuple(ref for ref in (self.incoming(node), self.outgoing(node)) if ref is not None)

    def anchor_of(self, ref: ControlRef) -> int:
        seg, which = ref
        if which == 1:
            return self.owner_of.get(seg - 1, seg - 1)
        return self.owner_of.get(seg, seg)

    def opposite(self, ref: ControlRef) -> ControlRef | None:
        node = self.anchor_of(ref)
        return self.incoming(node) if ref[1] == 1 else self.outgoing(node)


def control_point(segments: Segments, ref: ControlRef) -> Point:
    s = segments[ref[0]]
    assert isinstance(s, CubicTo)
    return (s.c1x, s.c1y) if ref[1] == 1 else (s.c2x, s.c2y)


def _set_control(segments: list[Segment], ref: ControlRef, p: Point) -> None:
    s = segments[ref[0]]
    assert isinstance(s, CubicTo)
    segments[ref[0]] = replace(s, c1x=p[0], c1y=p[1]) if ref[1] == 1 else replace(s, c2x=p[0], c2y=p[1])


def _is_smooth(segments: Segments, topo: _Topology, node: int) -> bool:
    a, b = topo.incoming(node), topo.outgoing(node)
    if a is None or b is None:
        return False
    anchor = _end(segments[node])
    pa, pb = control_point(segments, a), control_point(segments, b)
    va, vb = (pa[0] - anchor[0], pa[1] - anchor[1]), (pb[0] - anchor[0], pb[1] - anchor[1])
    la, lb = math.hypot(*va), math.hypot(*vb)
    if la < _SAME_POINT or lb < _SAME_POINT:
        return False
    cos = (va[0] * vb[0] + va[1] * vb[1]) / (la * lb)
    return cos <= -math.cos(math.radians(_SMOOTH_DEG))


def nodes(segments: Segments) -> list[NodeInfo]:
    topo = _Topology(segments)
    return [
        NodeInfo(i, _end(segments[i]), topo.controls(i), _is_smooth(segments, topo, i)) for i in topo.node_indices()
    ]


def visible_controls(segments: Segments, selected) -> set[ControlRef]:
    """Both controls of every curve segment next to a selected node (what the Node tool shows)."""
    topo = _Topology(segments)
    out: set[ControlRef] = set()
    for node in selected:
        if not topo.is_node(node):
            continue
        for seg in (topo.alias_of.get(node, node), node + 1):
            if seg < len(segments) and isinstance(segments[seg], CubicTo):
                out.update({(seg, 1), (seg, 2)})
    return out


def control_anchor(segments: Segments, ref: ControlRef) -> Point:
    """The anchor a control's arm is drawn from."""
    return _end(segments[_Topology(segments).anchor_of(ref)])


def valid_nodes(segments: Segments, indices) -> set[int]:
    topo = _Topology(segments)
    return {i for i in indices if topo.is_node(i)}


def move_nodes(segments: Segments, indices, dx: float, dy: float) -> Segments:
    """Moves the anchors with their aliases and attached control points."""
    topo = _Topology(segments)
    out = list(segments)
    ends: set[int] = set()
    controls: set[ControlRef] = set()
    for node in indices:
        if not topo.is_node(node):
            continue
        ends.add(node)
        if node in topo.alias_of:
            ends.add(topo.alias_of[node])
        controls.update(topo.controls(node))
    for i in ends:
        x, y = _end(out[i])
        out[i] = replace(out[i], x=x + dx, y=y + dy)
    for ref in controls:
        x, y = control_point(out, ref)
        _set_control(out, ref, (x + dx, y + dy))
    return tuple(out)


def move_control(segments: Segments, ref: ControlRef, point: Point, keep_smooth: bool = True) -> Segments:
    """Moves one control point; a smooth node's opposite control turns with it, keeping its own length."""
    topo = _Topology(segments)
    node = topo.anchor_of(ref)
    smooth = keep_smooth and _is_smooth(segments, topo, node)
    out = list(segments)
    _set_control(out, ref, point)
    opposite = topo.opposite(ref)
    if smooth and opposite is not None:
        ax, ay = _end(segments[node])
        ox, oy = control_point(segments, opposite)
        length = math.hypot(ox - ax, oy - ay)
        vx, vy = point[0] - ax, point[1] - ay
        dist = math.hypot(vx, vy)
        if dist > _SAME_POINT:
            _set_control(out, opposite, (ax - vx / dist * length, ay - vy / dist * length))
    return tuple(out)


# --- picking on segments ------------------------------------------------------


def _segment_start(segments: Segments, i: int) -> Point:
    return _end(segments[i - 1])


def _eval(segments: Segments, topo: _Topology, i: int, t: float) -> Point:
    s = segments[i]
    p0 = _segment_start(segments, i)
    if isinstance(s, CubicTo):
        mt = 1 - t
        a, b, c, d = mt**3, 3 * mt * mt * t, 3 * mt * t * t, t**3
        return (
            a * p0[0] + b * s.c1x + c * s.c2x + d * s.x,
            a * p0[1] + b * s.c1y + c * s.c2y + d * s.y,
        )
    p1 = _end(segments[topo.subpath_of[i].start]) if isinstance(s, Close) else _end(s)
    return p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t


def nearest_on_path(segments: Segments, point: Point) -> tuple[int, float, float] | None:
    """(segment index, t, distance) of the closest point on any drawn segment, including implicit closing lines."""
    topo = _Topology(segments)
    best: tuple[float, int, float] | None = None

    def dist(i: int, t: float) -> float:
        x, y = _eval(segments, topo, i, t)
        return math.hypot(x - point[0], y - point[1])

    for i, s in enumerate(segments):
        if isinstance(s, Close):
            # With an explicit closing segment the Close itself spans zero length.
            if topo.subpath_of[i].alias is not None:
                continue
        elif not _is_drawn(s):
            continue
        t_best = min((k / _SAMPLES for k in range(_SAMPLES + 1)), key=lambda t: dist(i, t))
        lo, hi = max(0.0, t_best - 1 / _SAMPLES), min(1.0, t_best + 1 / _SAMPLES)
        for _ in range(30):
            m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
            if dist(i, m1) < dist(i, m2):
                hi = m2
            else:
                lo = m1
        t = (lo + hi) / 2
        d = dist(i, t)
        if best is None or d < best[0]:
            best = (d, i, t)
    return None if best is None else (best[1], best[2], best[0])


def insert_node(segments: Segments, index: int, t: float) -> tuple[Segments, int]:
    """Splits segment `index` at `t` without changing the shape; returns the new segments and the new node index."""
    topo = _Topology(segments)
    s = segments[index]
    p = _eval(segments, topo, index, t)
    out = list(segments)
    if isinstance(s, CubicTo):
        p0 = _segment_start(segments, index)
        c1, c2, p3 = (s.c1x, s.c1y), (s.c2x, s.c2y), (s.x, s.y)
        a = _lerp(p0, c1, t)
        b = _lerp(c1, c2, t)
        c = _lerp(c2, p3, t)
        ab, bc = _lerp(a, b, t), _lerp(b, c, t)
        out[index : index + 1] = [CubicTo(*a, *ab, *p), CubicTo(*bc, *c, *p3)]
    elif isinstance(s, LineTo):
        out[index : index + 1] = [LineTo(*p), s]
    elif isinstance(s, Close):
        out.insert(index, LineTo(*p))
    else:
        raise ValueError("can't insert a node on a MoveTo")
    return tuple(out), index


def _lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


# --- deleting -----------------------------------------------------------------

# An edge from one anchor to the next: None for a straight line, else its two control points.
_Edge = tuple[Point, Point] | None


def delete_nodes(segments: Segments, indices) -> Segments | None:
    """Removes nodes, joining their neighbours; subpaths left with fewer than 2 nodes go. None when nothing is left."""
    topo = _Topology(segments)
    doomed = {i for i in indices if topo.is_node(i)}
    out: list[Segment] = []
    for sp in topo.subpaths:
        anchors, edges = _anchors_and_edges(segments, sp)
        keep = [k for k, (index, _) in enumerate(anchors) if index not in doomed]
        if len(keep) < 2:
            continue
        out.extend(_rebuild(anchors, edges, keep, sp.closed))
    return tuple(out) or None


def _anchors_and_edges(segments: Segments, sp: _Subpath) -> tuple[list[tuple[int, Point]], list[_Edge]]:
    anchors: list[tuple[int, Point]] = [(sp.start, _end(segments[sp.start]))]
    edges: list[_Edge] = []
    for i in range(sp.start + 1, sp.end):
        s = segments[i]
        if isinstance(s, Close):
            if sp.alias is None:
                edges.append(None)
            continue
        edges.append(((s.c1x, s.c1y), (s.c2x, s.c2y)) if isinstance(s, CubicTo) else None)
        if i != sp.alias:
            anchors.append((i, _end(s)))
    return anchors, edges


def _rebuild(anchors: list[tuple[int, Point]], edges: list[_Edge], keep: list[int], closed: bool) -> list[Segment]:
    n = len(anchors)
    out: list[Segment] = [MoveTo(*anchors[keep[0]][1])]
    pairs = list(zip(keep, keep[1:]))
    if closed:
        pairs.append((keep[-1], keep[0]))
    for a, b in pairs:
        span = range(a, b if b > a else b + n)
        merged = [edges[k % n] for k in span]
        target = anchors[b][1]
        if all(e is None for e in merged):
            if not (closed and b == keep[0]):
                out.append(LineTo(*target))
            continue
        c1 = merged[0][0] if merged[0] is not None else anchors[a][1]
        c2 = merged[-1][1] if merged[-1] is not None else target
        out.append(CubicTo(*c1, *c2, *target))
    if closed:
        out.append(Close())
    return out
