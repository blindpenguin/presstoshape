import pytest

from tests.helpers import all_shapes
from veccy.editing.operations import shapes
from veccy.editing.session import Session
from veccy.models.shapes import RectShape


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
