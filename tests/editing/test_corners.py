from dataclasses import replace

from presstoshape.editing import queries, registry
from presstoshape.editing.operations import booleans, corners, node_editing, paths, selection, shapes, view
from presstoshape.editing.session import Session
from presstoshape.geometry import corners as corner_geometry
from presstoshape.geometry import transforms
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import CubicTo, LineTo, MoveTo, PathShape, Rounding
from tests.helpers import all_shapes

SQUARE = rect_segments(0, 0, 100, 100)
OPEN = (MoveTo(0, 0), LineTo(100, 0), LineTo(100, 100))


def _session(*segment_lists):
    session = Session()
    ids = [shapes.add_drawn_path(session, segments, Tool.PEN) for segments in segment_lists]
    selection.set_selection(session, set(ids))
    return session, ids


def _roundings(session, sid):
    segments = queries.find_shape(session.state, sid).segments
    return {i: s.rounding for i, s in enumerate(segments) if getattr(s, "rounding", None)}


def test_set_radius_only_touches_roundable_nodes_in_one_step():
    session, (sid,) = _session(OPEN)
    depth = session.undo_count
    corners.set_radius(session, {(sid, 0), (sid, 1), (sid, 2)}, 10)
    assert _roundings(session, sid) == {1: Rounding(10)}
    assert session.undo_count == depth + 1 and session.undo_label == "Round corners"
    corners.set_radius(session, {(sid, 1)}, 0)
    assert _roundings(session, sid) == {}


def test_set_radius_keeps_the_kind_and_set_corners_changes_it():
    session, (sid,) = _session(SQUARE)
    corners.set_corners(session, {(sid, 0), (sid, 2)}, "chamfer", 5)
    corners.set_radius(session, {(sid, 0), (sid, 1)}, 8)
    assert _roundings(session, sid) == {0: Rounding(8, "chamfer"), 1: Rounding(8), 2: Rounding(5, "chamfer")}


def test_spinbox_steps_merge():
    session, (sid,) = _session(SQUARE)
    depth = session.undo_count
    for radius in (1, 2, 3):
        corners.set_radius(session, {(sid, 1)}, radius, merge_key="corner_radius")
    assert session.undo_count == depth + 1 and _roundings(session, sid) == {1: Rounding(3)}


def test_selected_corner_values():
    session, (sid,) = _session(SQUARE)
    view.select_tool(session, Tool.NODE)
    assert corners.selected_corner_values(session.state) is None
    node_editing.set_node_selection(session, {(sid, 0), (sid, 1)})
    assert corners.selected_corner_values(session.state) == ("round", 0.0)
    corners.set_corners(session, {(sid, 0)}, "inverted", 4)
    assert corners.selected_corner_values(session.state) == (None, None)


def test_remove_with_and_without_node_selection():
    session, (sid,) = _session(SQUARE)
    corners.set_radius(session, {(sid, i) for i in range(4)}, 6)
    view.select_tool(session, Tool.NODE)
    node_editing.set_node_selection(session, {(sid, 0)})
    registry.find("path.remove_corners").invoke(session)
    assert set(_roundings(session, sid)) == {1, 2, 3}
    view.select_tool(session, Tool.SELECT)
    registry.find("path.remove_corners").invoke(session)
    assert _roundings(session, sid) == {}
    assert not registry.find("path.remove_corners").can_run(session)


def test_apply_bakes_the_outline_in_place():
    session, (sid,) = _session(SQUARE)
    corners.set_radius(session, {(sid, 2)}, 10)
    before = queries.find_shape(session.state, sid)
    _run = registry.find("path.apply_corners")
    assert _run.can_run(session)
    _run.invoke(session)
    after = queries.find_shape(session.state, sid)
    assert after.id == sid and after.style == before.style
    assert after.segments == corner_geometry.rounded(before.segments)
    assert sum(isinstance(s, CubicTo) for s in after.segments) == 1
    assert session.undo_label == "Apply corner rounding"
    assert not _run.can_run(session)


def test_object_to_path_bakes_live_corners():
    session, (sid,) = _session(SQUARE)
    corners.set_radius(session, {(sid, 2)}, 10)
    assert queries.can_object_to_path(session.state)
    paths.object_to_path(session)
    assert not corner_geometry.has_rounding(queries.find_shape(session.state, sid).segments)


def test_booleans_use_the_rounded_outline():
    session, (a,) = _session(SQUARE)
    corners.set_radius(session, {(a, 2)}, 40)
    b = shapes.add_rectangle(session, (200, 200), (210, 210))
    selection.set_selection(session, {a, b})
    booleans.combine(session, "union")
    (result,) = all_shapes(session)
    assert isinstance(result, PathShape)
    assert any(isinstance(s, CubicTo) for s in result.segments)
    points = [(round(s.x, 3), round(s.y, 3)) for s in result.segments if hasattr(s, "x")]
    assert (100.0, 100.0) not in points


def test_roundings_survive_moving_and_scaling():
    session, (sid,) = _session(SQUARE)
    corners.set_radius(session, {(sid, 2)}, 10)
    shape = queries.find_shape(session.state, sid)
    scaled = transforms.transform_shape(shape, (2.0, 0.0, 0.0, 2.0, 0.0, 0.0))
    assert scaled.segments[2].rounding == Rounding(10)
    assert replace(shape, segments=shape.segments).segments[2].rounding == Rounding(10)
