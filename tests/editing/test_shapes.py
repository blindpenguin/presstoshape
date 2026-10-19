import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import shapes
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import RectShape
from tests.helpers import all_shapes


def test_add_rectangle_selects_it_and_marks_dirty():
    session = Session()
    sid = shapes.add_rectangle(session, (10, 10), (0, 0))
    assert session.state.selection == {sid}
    assert isinstance(all_shapes(session)[0], RectShape)
    assert session.state.dirty


def test_tiny_drag_adds_nothing():
    session = Session()
    assert shapes.add_rectangle(session, (0, 0), (0.5, 20)) is None
    assert not session.can_undo


def test_set_shape_field_edits_geometry_with_merged_undo():
    session = Session()
    sid = shapes.add_rectangle(session, (0, 0), (10, 10))
    for w in (20, 30, 40):
        shapes.set_shape_field(session, sid, "width", w)
    shapes.set_shape_field(session, sid, "x", 5)
    assert (all_shapes(session)[0].width, all_shapes(session)[0].x) == (40, 5)
    session.undo()
    assert (all_shapes(session)[0].width, all_shapes(session)[0].x) == (40, 0)
    session.undo()
    assert all_shapes(session)[0].width == 10


def test_set_shape_field_clamps_sizes_and_rejects_empty_text():
    session = Session()
    sid = shapes.add_ellipse(session, (0, 0), (10, 10))
    shapes.set_shape_field(session, sid, "rx", -5)
    assert all_shapes(session)[0].rx == 0.1
    tid = shapes.add_text(session, (0, 0), "hello")
    shapes.set_shape_field(session, tid, "text", "   ")
    shapes.set_shape_field(session, tid, "text", "bye")
    assert all_shapes(session)[1].text == "bye"


def test_set_shape_field_rejects_fields_of_other_shape_types():
    session = Session()
    sid = shapes.add_rectangle(session, (0, 0), (10, 10))
    with pytest.raises(ValueError):
        shapes.set_shape_field(session, sid, "rx", 3)


def test_drawn_paths_use_the_tools_style_and_land_like_other_shapes():
    from presstoshape.editing.operations import composites, layers, selection, view
    from presstoshape.models.shapes import LineTo, MoveTo

    segments = (MoveTo(0, 0), LineTo(50, 50))
    session = Session()
    path_id = shapes.add_drawn_path(session, segments, Tool.PENCIL)
    (path,) = all_shapes(session)
    assert path.id == path_id and path.segments == segments
    assert path.style == session.state.tool_styles[Tool.PENCIL] and path.style.fill is None
    assert session.undo_label == "Add path" and session.state.selection == {path_id}

    bottom = shapes.add_rectangle(session, (0, 0), (10, 10))
    top = shapes.add_rectangle(session, (5, 5), (15, 15))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session)
    (composite,) = session.state.selection
    composites.enter(session, composite)
    composites.set_new_part_mode(session, "subtract")
    part = shapes.add_drawn_path(session, segments, Tool.PENCIL)
    assert queries.find_shape(session.state, composite).modes[-1] == "subtract"
    assert queries.find_shape(session.state, part) is not None

    composites.leave_all(session.state)
    layers.set_layer_visible(session, 0, False)
    assert shapes.add_drawn_path(session, segments, Tool.PENCIL) is None
    assert "hidden" in session.state.status_message

    view.set_pencil_smoothing(session, 140)
    assert session.state.pencil_smoothing == 100
    session.state.dirty = False
    view.set_pencil_smoothing(session, -3)
    assert session.state.pencil_smoothing == 0 and not session.state.dirty
