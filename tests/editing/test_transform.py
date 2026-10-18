import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import shapes, transform
from presstoshape.editing.session import Session
from presstoshape.geometry import affine, transforms


def _rect_session(rotation: float = 0.0):
    session = Session()
    sid = shapes.add_rectangle(session, (0, 0), (20, 10))
    if rotation:
        transform.set_rotation(session, sid, rotation)
    return session, sid


def test_transform_selection_is_one_undo_step():
    session, sid = _rect_session()
    undo_depth = session.undo_count
    transform.transform_selection(session, affine.scaling(2, 2))
    assert session.undo_count == undo_depth + 1
    rect = queries.find_shape(session.state, sid)
    assert (rect.width, rect.height) == (40, 20)
    session.undo()
    assert queries.find_shape(session.state, sid).width == 20


def test_transform_selection_ignores_identity_and_singular():
    session, _ = _rect_session()
    undo_depth = session.undo_count
    transform.transform_selection(session, affine.IDENTITY)
    transform.transform_selection(session, affine.scaling(0, 1))
    assert session.undo_count == undo_depth


def test_set_rotation_merges_consecutive_edits():
    session, sid = _rect_session()
    undo_depth = session.undo_count
    transform.set_rotation(session, sid, 10)
    transform.set_rotation(session, sid, 20)
    assert session.undo_count == undo_depth + 1
    assert transforms.rotation_of(queries.find_shape(session.state, sid)) == pytest.approx(20)
    session.undo()
    assert transforms.rotation_of(queries.find_shape(session.state, sid)) == 0


def test_set_rotation_ignores_skewed_shapes():
    session, sid = _rect_session()
    transform.transform_selection(session, affine.compose(affine.scaling(2, 1), affine.rotation(0.5)))
    skewed = queries.find_shape(session.state, sid)
    assert transforms.rotation_of(skewed) is None
    transform.set_rotation(session, sid, 10)
    assert queries.find_shape(session.state, sid) == skewed


def test_editing_x_keeps_rotation_about_new_center():
    session, sid = _rect_session(rotation=30)
    shapes.set_shape_field(session, sid, "x", 100)
    rect = queries.find_shape(session.state, sid)
    angle, cx, cy = affine.as_rotation(rect.transform)
    assert angle == pytest.approx(30)
    assert (cx, cy) == pytest.approx((110, 5))
