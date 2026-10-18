import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import paths, selection, shapes, transform
from presstoshape.editing.session import Session
from presstoshape.models.shapes import EllipseShape, PathShape, RectShape
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
