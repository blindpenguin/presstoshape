"""Live corners: the outline of a path whose corner nodes carry a `Rounding`, drawn round, inverted or chamfered
while the nodes stay where they are. Pure functions; `transforms.outline` draws with them and the Node tool places
its corner widgets with them.

A corner node is rounded when it has a segment on both sides, isn't smooth and has a usable angle. Its cut length
on both sides is the tangent length of a circle of the stored radius touching both directions. Neighbouring
roundings never overlap: a segment rounded at both ends gives each end at most half its length, otherwise all of
it. A rounding cut back that way is drawn smaller and reported by `limited`; the stored radius stays.
"""

import math
from dataclasses import dataclass, replace

from presstoshape.geometry import nodes
from presstoshape.geometry.boxes import Point
from presstoshape.geometry.path_edit import Sub, to_subs
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Rounding, Segment

Segments = tuple[Segment, ...]
Cubic = tuple[Point, Point, Point, Point]

_TINY = 1e-9
# Corners closer than this to straight or folded back (radians) can't be rounded.
_MIN_ANGLE = 1e-3
_SAMPLES = 32


def has_rounding(segments: Segments) -> bool:
    return any(getattr(segment, "rounding", None) is not None for segment in segments)


# --- vectors and cubics -------------------------------------------------------------


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _add(a: Point, v: Point, f: float = 1.0) -> Point:
    return a[0] + v[0] * f, a[1] + v[1] * f


def _unit(v: Point) -> Point | None:
    length = math.hypot(*v)
    return None if length < _TINY else (v[0] / length, v[1] / length)


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _point(c: Cubic, t: float) -> Point:
    p0, p1, p2, p3 = c
    mt = 1 - t
    a, b, cc, d = mt**3, 3 * mt * mt * t, 3 * mt * t * t, t**3
    return a * p0[0] + b * p1[0] + cc * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + cc * p2[1] + d * p3[1]


def split(c: Cubic, t: float) -> tuple[Cubic, Cubic]:
    """de Casteljau: the parts of `c` before and after `t`."""
    p0, p1, p2, p3 = c
    a, b, d = _lerp(p0, p1, t), _lerp(p1, p2, t), _lerp(p2, p3, t)
    ab, bd = _lerp(a, b, t), _lerp(b, d, t)
    m = _lerp(ab, bd, t)
    return (p0, a, ab, m), (m, bd, d, p3)


def _between(c: Cubic, t0: float, t1: float) -> Cubic:
    if t1 < 1:
        c = split(c, t1)[0]
        t0 = t0 / t1 if t1 > _TINY else 0.0
    return split(c, t0)[1] if t0 > 0 else c


# --- edges ---------------------------------------------------------------------------


@dataclass
class _Edge:
    """One segment of a subpath as a cubic (lines with controls on their ends) and its arc-length table."""

    cubic: Cubic
    line: bool
    _table: list[float] | None = None

    @property
    def table(self) -> list[float]:
        if self._table is None:
            if self.line:
                self._table = [math.dist(self.cubic[0], self.cubic[3])]
            else:
                points = [_point(self.cubic, k / _SAMPLES) for k in range(_SAMPLES + 1)]
                total, lengths = 0.0, [0.0]
                for a, b in zip(points, points[1:]):
                    total += math.dist(a, b)
                    lengths.append(total)
                self._table = lengths
        return self._table

    @property
    def length(self) -> float:
        return self.table[-1]

    def t_at(self, distance: float) -> float:
        """Parameter at arc length `distance` from the start."""
        length = self.length
        if length < _TINY:
            return 0.0
        if self.line:
            return min(max(distance / length, 0.0), 1.0)
        table = self.table
        distance = min(max(distance, 0.0), length)
        for k in range(1, len(table)):
            if table[k] >= distance:
                span = table[k] - table[k - 1]
                f = (distance - table[k - 1]) / span if span > _TINY else 0.0
                return (k - 1 + f) / _SAMPLES
        return 1.0

    def start_direction(self) -> Point | None:
        p0, c1, c2, p3 = self.cubic
        return _unit(_sub(c1, p0)) or _unit(_sub(c2, p0)) or _unit(_sub(p3, p0))

    def end_direction(self) -> Point | None:
        p0, c1, c2, p3 = self.cubic
        return _unit(_sub(p3, c2)) or _unit(_sub(p3, c1)) or _unit(_sub(p3, p0))

    def piece(self, t0: float, t1: float) -> Cubic:
        if self.line:
            return self.cubic[0], self.cubic[0], self.cubic[3], self.cubic[3]
        return _between(self.cubic, t0, t1)

    def line_points(self, t0: float, t1: float) -> tuple[Point, Point]:
        return _lerp(self.cubic[0], self.cubic[3], t0), _lerp(self.cubic[0], self.cubic[3], t1)


def _edges(sub: Sub) -> list[_Edge]:
    out = []
    n = len(sub.anchors)
    for e, edge in enumerate(sub.edges):
        a, b = sub.anchors[e].point, sub.anchors[(e + 1) % n].point
        out.append(_Edge((a, a, b, b), True) if edge is None else _Edge((a, edge[0], edge[1], b), False))
    return out


# --- corners -------------------------------------------------------------------------


@dataclass
class _Corner:
    """A corner node that can be rounded: where it is, its sides and its interior angle."""

    sub: int
    k: int
    index: int
    point: Point
    into: Point  # direction of travel arriving at the node
    out: Point  # direction of travel leaving it
    angle: float  # interior angle, radians
    rounding: Rounding | None


@dataclass
class _Cut:
    """How far a rounded corner reaches along its two segments, and the parameters where it does."""

    distance: float
    wanted: float
    t_in: float
    t_out: float


def _corners(segments: Segments) -> tuple[list[Sub], list[list[_Edge]], dict[int, _Corner]]:
    smooth = {info.index: info.smooth for info in nodes.nodes(segments)}
    subs = to_subs(segments)
    all_edges = [_edges(sub) for sub in subs]
    corners: dict[int, _Corner] = {}
    for s, (sub, edges) in enumerate(zip(subs, all_edges)):
        n = len(sub.anchors)
        if n < 2:
            continue
        for k, anchor in enumerate(sub.anchors):
            if anchor.source is None or smooth.get(anchor.source, False):
                continue
            if not sub.closed and (k == 0 or k == n - 1):
                continue
            into, out = edges[(k - 1) % n].end_direction(), edges[k % n].start_direction()
            if into is None or out is None:
                continue
            angle = math.acos(max(-1.0, min(1.0, _dot((-into[0], -into[1]), out))))
            if angle < _MIN_ANGLE or angle > math.pi - _MIN_ANGLE:
                continue
            corners[anchor.source] = _Corner(s, k, anchor.source, anchor.point, into, out, angle, anchor.rounding)
    return subs, all_edges, corners


def _cuts(subs: list[Sub], all_edges: list[list[_Edge]], corners: dict[int, _Corner]) -> dict[int, _Cut]:
    rounded = {i: c for i, c in corners.items() if c.rounding is not None and c.rounding.radius > 0}
    at = {(c.sub, c.k) for c in rounded.values()}
    cuts: dict[int, _Cut] = {}
    for index, c in rounded.items():
        assert c.rounding is not None
        n = len(subs[c.sub].anchors)
        edge_in, edge_out = all_edges[c.sub][(c.k - 1) % n], all_edges[c.sub][c.k % n]
        # A segment rounded at both ends gives each end half of it.
        share_in = 0.5 if (c.sub, (c.k - 1) % n) in at else 1.0
        share_out = 0.5 if (c.sub, (c.k + 1) % n) in at else 1.0
        wanted = c.rounding.radius / math.tan(c.angle / 2)
        distance = min(wanted, edge_in.length * share_in, edge_out.length * share_out)
        if distance < _TINY:
            continue
        cuts[index] = _Cut(distance, wanted, edge_in.t_at(edge_in.length - distance), edge_out.t_at(distance))
    return cuts


def _round_piece(p_in: Point, into: Point, p_out: Point, out: Point) -> Segment:
    turn = math.acos(max(-1.0, min(1.0, _dot(into, out))))
    chord = math.dist(p_in, p_out)
    if turn < _TINY or chord < _TINY:
        return LineTo(*p_out)
    radius = chord / (2 * math.sin(turn / 2))
    h = 4 / 3 * math.tan(turn / 4) * radius
    c1, c2 = _add(p_in, into, h), _add(p_out, out, -h)
    return CubicTo(*c1, *c2, *p_out)


def _inverted_piece(node: Point, p_in: Point, p_out: Point) -> Segment:
    """A concave arc around the node from `p_in` to `p_out`."""
    r_in, r_out = _sub(p_in, node), _sub(p_out, node)
    ra, rb = math.hypot(*r_in), math.hypot(*r_out)
    if ra < _TINY or rb < _TINY:
        return LineTo(*p_out)
    sweep = math.acos(max(-1.0, min(1.0, _dot(r_in, r_out) / (ra * rb))))
    radius = (ra + rb) / 2
    h = 4 / 3 * math.tan(sweep / 4) * radius
    chord = _sub(p_out, p_in)
    t_in = (-r_in[1] / ra, r_in[0] / ra)
    if _dot(t_in, chord) < 0:
        t_in = (-t_in[0], -t_in[1])
    t_out = (-r_out[1] / rb, r_out[0] / rb)
    if _dot(t_out, chord) < 0:
        t_out = (-t_out[0], -t_out[1])
    c1, c2 = _add(p_in, t_in, h), _add(p_out, t_out, -h)
    return CubicTo(*c1, *c2, *p_out)


def _edge_segment(edge: _Edge, t0: float, t1: float) -> Segment:
    if edge.line:
        return LineTo(*edge.line_points(t0, t1)[1])
    _p0, c1, c2, p3 = edge.piece(t0, t1)
    return CubicTo(*c1, *c2, *p3)


def _cut_point(edge: _Edge, t: float) -> tuple[Point, Point]:
    """Point at `t` and the direction of travel there."""
    if edge.line:
        direction = edge.start_direction() or (1.0, 0.0)
        return _lerp(edge.cubic[0], edge.cubic[3], t), direction
    before, after = split(edge.cubic, t)
    direction = _unit(_sub(after[1], after[0])) or _unit(_sub(before[3], before[2])) or (1.0, 0.0)
    return before[3], direction


def rounded(segments: Segments) -> Segments:
    """The outline as drawn: every rounded corner replaced by its arc or cut. Segments without roundings come back
    as they are (the same tuple)."""
    if not has_rounding(segments):
        return segments
    subs, all_edges, corners = _corners(segments)
    cuts = _cuts(subs, all_edges, corners)
    by_position = {(corners[i].sub, corners[i].k): (corners[i], cut) for i, cut in cuts.items()}
    out: list[Segment] = []
    for s, (sub, edges) in enumerate(zip(subs, all_edges)):
        n = len(sub.anchors)
        if n == 0:
            continue

        def corner_piece(k: int) -> Segment:
            corner, cut = by_position[(s, k)]
            p_in, into = _cut_point(edges[(k - 1) % n], cut.t_in)
            p_out, leave = _cut_point(edges[k % n], cut.t_out)
            assert corner.rounding is not None
            if corner.rounding.kind == "chamfer":
                return LineTo(*p_out)
            if corner.rounding.kind == "inverted":
                return _inverted_piece(corner.point, p_in, p_out)
            return _round_piece(p_in, into, p_out, leave)

        first = by_position.get((s, 0))
        start = _cut_point(edges[0], first[1].t_out)[0] if first is not None else sub.anchors[0].point
        out.append(MoveTo(*start))
        for e, edge in enumerate(edges):
            if e > 0 and (s, e) in by_position:
                out.append(corner_piece(e))
            t0 = by_position[(s, e)][1].t_out if (s, e) in by_position else 0.0
            end = (e + 1) % n
            t1 = by_position[(s, end)][1].t_in if (s, end) in by_position and (sub.closed or end != 0) else 1.0
            out.append(_edge_segment(edge, t0, t1))
        if sub.closed:
            if first is not None:
                out.append(corner_piece(0))
            elif out and isinstance(out[-1], LineTo):
                # The closing line is drawn by Close.
                out.pop()
            out.append(Close())
    return tuple(out)


def limited(segments: Segments) -> set[int]:
    """Rounded nodes drawn smaller than their stored radius because the segments are too short."""
    if not has_rounding(segments):
        return set()
    subs, all_edges, corners = _corners(segments)
    return {i for i, cut in _cuts(subs, all_edges, corners).items() if cut.distance < cut.wanted - 1e-6}


def roundable(segments: Segments) -> set[int]:
    """Corner nodes that can carry a rounding: a segment on both sides, not smooth, a usable angle."""
    return set(_corners(segments)[2])


def _arc_middle(radius: float, angle: float) -> float:
    """Distance from the node to the middle of a round corner of `radius`."""
    return radius / math.sin(angle / 2) - radius


def widget(segments: Segments, index: int, min_distance: float) -> Point | None:
    """Where the corner widget of node `index` sits: inside the angle on its bisector, `min_distance` from the
    node or on the rounded curve when that is further."""
    subs, all_edges, corners = _corners(segments)
    corner = corners.get(index)
    if corner is None:
        return None
    direction = _unit(_sub(corner.out, corner.into))
    if direction is None:
        return None
    cut = _cuts(subs, all_edges, corners).get(index)
    radius = cut.distance * math.tan(corner.angle / 2) if cut is not None else 0.0
    return _add(corner.point, direction, max(min_distance, _arc_middle(radius, corner.angle)))


def bisector(segments: Segments, index: int) -> tuple[Point, Point] | None:
    """(node point, unit direction into the corner) for a roundable node."""
    corner = _corners(segments)[2].get(index)
    if corner is None:
        return None
    direction = _unit(_sub(corner.out, corner.into))
    return None if direction is None else (corner.point, direction)


def radius_for(segments: Segments, index: int, distance: float) -> float:
    """The radius whose round curve passes `distance` from the node along the bisector (inverse of the widget's
    placement); 0 when the distance is 0 or less."""
    corner = _corners(segments)[2].get(index)
    if corner is None or distance <= 0:
        return 0.0
    return distance / (1 / math.sin(corner.angle / 2) - 1)


def drawn_radius(segments: Segments, index: int) -> float:
    """The radius node `index` is drawn with (smaller than stored when limited), 0 when not rounded."""
    subs, all_edges, corners = _corners(segments)
    corner = corners.get(index)
    if corner is None:
        return 0.0
    cut = _cuts(subs, all_edges, corners).get(index)
    return 0.0 if cut is None else cut.distance * math.tan(corner.angle / 2)


def widgets(
    segments: Segments, indices: set[int] | None, min_distance: float, min_side: float
) -> list[tuple[int, Point]]:
    """Corner widgets for the given nodes (all roundable ones when None): (node index, position). Corners whose
    shorter side is under `min_side` get none, they'd be too small to tell apart."""
    subs, all_edges, corners = _corners(segments)
    cuts = _cuts(subs, all_edges, corners)
    out = []
    for index, corner in corners.items():
        if indices is not None and index not in indices:
            continue
        n = len(subs[corner.sub].anchors)
        edges = all_edges[corner.sub]
        if min(edges[(corner.k - 1) % n].length, edges[corner.k % n].length) < min_side:
            continue
        direction = _unit(_sub(corner.out, corner.into))
        if direction is None:
            continue
        cut = cuts.get(index)
        radius = cut.distance * math.tan(corner.angle / 2) if cut is not None else 0.0
        out.append((index, _add(corner.point, direction, max(min_distance, _arc_middle(radius, corner.angle)))))
    return out


def with_radius(segments: Segments, indices, radius: float) -> Segments:
    """The nodes among `indices` that can be rounded get `radius` (keeping their kind, new ones round); 0 or less
    removes their rounding."""
    chosen = set(indices) & roundable(segments)
    if not chosen:
        return segments
    out = list(segments)
    for index in chosen:
        old = out[index].rounding
        out[index] = replace(
            out[index], rounding=Rounding(radius, old.kind if old is not None else "round") if radius > 0 else None
        )
    return tuple(out)
