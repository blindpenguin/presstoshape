import pytest

from presstoshape.editing.operations import groups, selection, shapes, transform
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.shapes import TextShape
from presstoshape.render.paths import PathCache
from tests.helpers import all_shapes


def _box(shape):
    box = PathCache().geometry_bounds(shape)
    return box.left(), box.top(), box.right(), box.bottom()


def test_held_nudges_are_one_undo_step():
    session = Session()
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, {rect})
    for _step in range(3):
        transform.nudge(session, 1, 0)
    transform.nudge(session, 0, -2)
    assert (all_shapes(session)[0].x, all_shapes(session)[0].y) == (3, -2)
    assert session.undo_label == "Nudge"
    session.undo()
    assert (all_shapes(session)[0].x, all_shapes(session)[0].y) == (0, 0)


def test_nudge_without_selection_does_nothing():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, set())
    transform.nudge(session, 1, 0)
    assert session.undo_label == "Add rectangle"


def test_flip_mirrors_the_selection_about_its_centre():
    session = Session()
    left = shapes.add_rectangle(session, (0, 0), (10, 10))
    right = shapes.add_ellipse(session, (40, 0), (60, 20))
    selection.set_selection(session, {left, right})
    assert find("object.flip_horizontal").can_run(session)
    transform.flip(session, horizontal=True)
    rect, ellipse = all_shapes(session)
    assert _box(rect) == pytest.approx((50, 0, 60, 10))
    assert _box(ellipse) == pytest.approx((0, 0, 20, 20))
    assert session.undo_label == "Flip horizontally"
    transform.flip(session, horizontal=False)
    assert _box(all_shapes(session)[0]) == pytest.approx((50, 10, 60, 20))


def test_flip_reaches_into_groups_and_keeps_text_readable():
    session = Session()
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    text = shapes.add_text(session, (30, 40), "Hi")
    selection.set_selection(session, {rect, text})
    groups.group(session)
    transform.flip(session, horizontal=True)
    (group,) = all_shapes(session)
    flipped_text = group.children[1]
    assert isinstance(flipped_text, TextShape) and flipped_text.transform == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    assert _box(group.children[0])[2] == pytest.approx(_box(group)[2])


def test_flip_is_disabled_without_selection():
    assert not find("object.flip_vertical").can_run(Session())
