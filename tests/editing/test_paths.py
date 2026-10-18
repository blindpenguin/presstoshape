import pytest

from tests.helpers import all_shapes
from veccy.editing import queries
from veccy.editing.operations import paths, selection, shapes, transform
from veccy.editing.session import Session
from veccy.models.shapes import EllipseShape, PathShape, RectShape
from veccy.render.paths import PathCache


def test_union_replaces_selection_at_bottom_position():
    session = Session()
    keep = shapes.add_rectangle(session, (100, 100), (110, 110))
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    b = shapes.add_ellipse(session, (5, 5), (15, 15))
    selection.set_selection(session, {a, b})
    assert queries.can_combine(session.state)
    paths.combine(session, "union")
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
