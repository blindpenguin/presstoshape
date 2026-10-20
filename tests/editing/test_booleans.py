import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import booleans, selection, shapes, style
from presstoshape.editing.session import Session
from presstoshape.geometry import booleans as boolean_geometry
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.shapes import PathShape, Style
from tests.helpers import all_shapes


def _area(shape) -> float:
    return boolean_geometry._to_skia(shape.segments).area


def _two_squares(session):
    keep = shapes.add_rectangle(session, (100, 100), (110, 110))
    bottom = shapes.add_rectangle(session, (0, 0), (10, 10))
    top = shapes.add_rectangle(session, (5, 5), (15, 15))
    selection.set_selection(session, {bottom, top})
    return keep, bottom, top


def test_union_replaces_selection_at_bottom_position():
    session = Session()
    keep = shapes.add_rectangle(session, (100, 100), (110, 110))
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    b = shapes.add_ellipse(session, (5, 5), (15, 15))
    selection.set_selection(session, {a, b})
    assert queries.can_combine(session.state)
    booleans.combine(session, "union")
    current = all_shapes(session)
    assert [s.id for s in current][0] == keep
    assert len(current) == 2 and isinstance(current[1], PathShape)
    assert session.state.selection == {current[1].id}
    session.undo()
    assert [s.id for s in all_shapes(session)] == [keep, a, b]


def test_cannot_combine_with_text():
    session = Session()
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    t = shapes.add_text(session, (0, 0), "x")
    selection.set_selection(session, {a, t})
    assert not queries.can_combine(session.state)


@pytest.mark.parametrize(
    "op, area, label",
    [("union", 175, "Union"), ("difference", 75, "Difference"), ("intersection", 25, "Intersection"),
     ("exclude", 150, "Exclude")],
)
def test_combine_operations(op, area, label):
    session = Session()
    keep, bottom, top = _two_squares(session)
    bottom_style = queries.find_shape(session.state, bottom).style
    booleans.combine(session, op)
    current = all_shapes(session)
    assert current[0].id == keep and len(current) == 2
    result = current[1]
    assert _area(result) == pytest.approx(area)
    assert result.style == bottom_style
    assert session.state.selection == {result.id}
    assert session.undo_label == label
    assert session.state.status_message == label


def test_empty_intersection_removes_shapes_and_reports():
    session = Session()
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    b = shapes.add_rectangle(session, (50, 50), (60, 60))
    selection.set_selection(session, {a, b})
    booleans.combine(session, "intersection")
    assert all_shapes(session) == []
    assert session.state.selection == set()
    assert session.state.status_message == "Intersection is empty"
    session.undo()
    assert [s.id for s in all_shapes(session)] == [a, b]


def test_divide_pieces_styles_order_and_selection():
    session = Session()
    keep, bottom, top = _two_squares(session)
    selection.set_selection(session, {top})
    style.set_fill(session, "#ff0000")
    selection.set_selection(session, {bottom, top})
    booleans.divide_selection(session)
    current = all_shapes(session)
    assert current[0].id == keep
    pieces = current[1:]
    assert len(pieces) == 3
    assert session.state.selection == {piece.id for piece in pieces}
    assert session.state.status_message == "Divided into 3 pieces"
    assert session.undo_label == "Divide"
    # The bottom-only piece keeps the bottom style and sits lowest; overlap and top-only pieces are red.
    fills = [piece.style.fill for piece in pieces]
    assert fills[0] != "#ff0000" and fills[1:] == ["#ff0000", "#ff0000"]
    assert sorted(round(_area(piece)) for piece in pieces) == [25, 75, 75]


def test_divide_is_one_undo_step_restoring_ids_and_order():
    session = Session()
    keep, bottom, top = _two_squares(session)
    depth = session.undo_count
    booleans.divide_selection(session)
    assert session.undo_count == depth + 1
    session.undo()
    assert [s.id for s in all_shapes(session)] == [keep, bottom, top]


def test_operations_need_two_outlines():
    session = Session()
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, {a})
    depth = session.undo_count
    booleans.combine(session, "intersection")
    booleans.divide_selection(session)
    assert session.undo_count == depth and len(all_shapes(session)) == 1


def test_unknown_operation_raises():
    with pytest.raises(ValueError):
        booleans.combine(Session(), "merge")


def test_union_keeps_the_hole_of_an_evenodd_shape():
    session = Session()
    ring = rect_segments(0, 0, 10, 10) + rect_segments(3, 3, 4, 4)
    layer = session.state.document.layers[0]
    layer.shapes += [
        PathShape(90, ring, Style(fill_rule="evenodd")),
        PathShape(91, rect_segments(20, 0, 5, 5), Style()),
    ]
    selection.set_selection(session, {90, 91})
    booleans.combine(session, "union")
    assert _area(all_shapes(session)[0]) == pytest.approx(84 + 25)
