import pytest

from presstoshape.editing import containers, queries, registry
from presstoshape.editing.operations import (
    composites,
    edit_mode,
    node_editing,
    paths,
    selection,
    shapes,
    transform,
    view,
)
from presstoshape.editing.session import Session
from presstoshape.geometry import nodes, path_edit
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import Close, EllipseShape, LineTo, MoveTo, PathShape, RectShape
from presstoshape.render.paths import PathCache
from tests.helpers import all_shapes


def test_object_to_path_keeps_id_place_style_and_outline():
    session = Session()
    below = shapes.add_rectangle(session, (0, 0), (5, 5))
    sid = shapes.add_ellipse(session, (0, 0), (20, 10))
    text = shapes.add_text(session, (0, 40), "Hi")
    transform.set_rotation(session, sid, 45)
    before = {s.id: s for s in all_shapes(session)}
    cache = PathCache()
    bounds = {i: cache.geometry_bounds(s) for i, s in before.items()}
    selection.set_selection(session, {sid, text})
    assert queries.can_object_to_path(session.state)
    paths.object_to_path(session)
    current = all_shapes(session)
    assert [s.id for s in current] == [below, sid, text]
    assert isinstance(current[0], RectShape)
    for shape in current[1:]:
        assert isinstance(shape, PathShape) and shape.style == before[shape.id].style
        after = PathCache().geometry_bounds(shape)
        assert (after.left(), after.top(), after.right(), after.bottom()) == pytest.approx(
            (bounds[shape.id].left(), bounds[shape.id].top(), bounds[shape.id].right(), bounds[shape.id].bottom()),
            abs=1e-3,
        )
    assert session.state.selection == {sid, text}
    assert not queries.can_object_to_path(session.state)
    session.undo()
    assert isinstance(queries.find_shape(session.state, sid), EllipseShape)


# --- combine, split, close, open, reverse -------------------------------------------

OPEN = (MoveTo(0, 0), LineTo(10, 0), LineTo(20, 10))
SQUARE = (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10), LineTo(0, 10), Close())
HOLE = (MoveTo(2, 2), LineTo(8, 2), LineTo(5, 8), Close())


def _session(*segment_lists):
    session = Session()
    ids = [shapes.add_drawn_path(session, segments, Tool.PEN) for segments in segment_lists]
    selection.set_selection(session, set(ids))
    return session, ids


def _run(session, command_id):
    entry = registry.find(command_id)
    assert entry.can_run(session)
    depth = session.undo_count
    entry.invoke(session)
    assert session.undo_count == depth + 1


def test_combine_keeps_the_topmost_id_style_and_place():
    session = Session()
    below = shapes.add_rectangle(session, (100, 100), (110, 110))
    rect = shapes.add_rectangle(session, (0, 0), (10, 20))
    path = shapes.add_drawn_path(session, HOLE, Tool.PEN)
    ellipse = shapes.add_ellipse(session, (30, 0), (50, 10))
    above = shapes.add_rectangle(session, (200, 200), (210, 210))
    top_style = queries.find_shape(session.state, ellipse).style
    selection.set_selection(session, {rect, path, ellipse})
    _run(session, "path.combine")
    assert session.undo_label == "Combine"
    assert [s.id for s in all_shapes(session)] == [below, ellipse, above]
    combined = queries.find_shape(session.state, ellipse)
    assert isinstance(combined, PathShape) and combined.style == top_style
    assert len(path_edit.to_subs(combined.segments)) == 3
    assert session.state.selection == {ellipse}
    session.undo()
    assert len(all_shapes(session)) == 5


def test_combine_needs_two_paths_rects_or_ellipses():
    session, (sid,) = _session(OPEN)
    assert not registry.find("path.combine").can_run(session)
    text = shapes.add_text(session, (0, 40), "Hi")
    selection.set_selection(session, {sid, text})
    assert not registry.find("path.combine").can_run(session)


def test_split_makes_one_path_per_subpath_in_place():
    session = Session()
    below = shapes.add_rectangle(session, (100, 100), (110, 110))
    sid = shapes.add_drawn_path(session, (*SQUARE, *HOLE), Tool.PEN)
    above = shapes.add_rectangle(session, (200, 200), (210, 210))
    selection.set_selection(session, {sid})
    _run(session, "path.split")
    current = all_shapes(session)
    assert [s.id for s in current][0] == below and current[-1].id == above
    assert [s.segments for s in current[1:3]] == [SQUARE, HOLE]
    assert current[1].id == sid and current[1].style == current[2].style
    assert session.state.selection == {current[1].id, current[2].id}


def test_split_needs_a_compound_path():
    session, _ids = _session(SQUARE)
    assert not registry.find("path.split").can_run(session)


def test_split_parts_of_a_composite_keep_their_mode():
    session, ids = _session(SQUARE, (*SQUARE, *HOLE))
    composites.make_composite(session, "subtract")
    [composite_id] = session.state.selection
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {ids[1]})
    mode = containers.part_mode(session.state, ids[1])
    _run(session, "path.split")
    assert {containers.part_mode(session.state, i) for i in session.state.selection} == {mode}


def test_close_open_and_reverse_whole_paths():
    session, (sid,) = _session(OPEN)
    assert not registry.find("path.open").can_run(session)
    _run(session, "path.close")
    assert queries.find_shape(session.state, sid).segments == (*OPEN, Close())
    assert not registry.find("path.close").can_run(session)
    _run(session, "path.open")
    assert len(nodes.nodes(queries.find_shape(session.state, sid).segments)) == 4
    _run(session, "path.reverse")
    assert session.undo_label == "Reverse Direction"
    assert queries.find_shape(session.state, sid).segments[0] == MoveTo(0, 0)


def test_node_selection_limits_close_open_and_reverse_to_its_subpaths():
    session, (sid,) = _session((*OPEN, MoveTo(0, 20), LineTo(10, 20), LineTo(10, 30)))
    view.select_tool(session, Tool.NODE)
    node_editing.set_node_selection(session, {(sid, 5)})
    _run(session, "path.reverse")
    segments = queries.find_shape(session.state, sid).segments
    assert segments[:3] == OPEN and segments[3] == MoveTo(10, 30)
    assert session.state.node_selection == {(sid, 3)}
    _run(session, "path.close")
    assert [sub.closed for sub in path_edit.to_subs(queries.find_shape(session.state, sid).segments)] == [False, True]


def test_path_commands_ignore_other_shapes():
    session, (sid,) = _session(OPEN)
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, {sid, rect})
    _run(session, "path.reverse")
    assert isinstance(queries.find_shape(session.state, rect), RectShape)
    selection.set_selection(session, {rect})
    assert not registry.find("path.reverse").can_run(session)
