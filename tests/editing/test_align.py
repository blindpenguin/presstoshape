import pytest

from presstoshape.editing.operations import align, edit_mode, groups, selection, shapes
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.render.paths import PathCache
from tests.helpers import all_shapes


def _box(shape):
    box = PathCache().geometry_bounds(shape)
    return box.left(), box.top(), box.right(), box.bottom()


def _three(session):
    ids = [
        shapes.add_rectangle(session, (0, 0), (10, 10)),
        shapes.add_ellipse(session, (40, 20), (60, 60)),
        shapes.add_rectangle(session, (100, 5), (130, 15)),
    ]
    selection.set_selection(session, set(ids))
    return ids


def test_align_left_to_the_selection_is_one_undo_step():
    session = Session()
    _three(session)
    align.align(session, "left")
    assert [_box(shape)[0] for shape in all_shapes(session)] == pytest.approx([0, 0, 0])
    assert session.undo_label == "Align left"
    session.undo()
    assert _box(all_shapes(session)[2])[0] == pytest.approx(100)


def test_align_to_the_artboard_and_single_objects_always_do():
    session = Session()
    rect = shapes.add_rectangle(session, (10, 10), (30, 30))
    selection.set_selection(session, {rect})
    align.align(session, "hcenter")
    width = session.state.document.width
    assert _box(all_shapes(session)[0])[0] == pytest.approx(width / 2 - 10)
    _three(session)
    align.set_align_reference(session, "artboard")
    align.align(session, "bottom")
    height = session.state.document.height
    assert all(_box(shape)[3] == pytest.approx(height) for shape in all_shapes(session)[1:])


def test_aligned_shapes_that_dont_move_make_no_undo_step():
    session = Session()
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (0, 50), (20, 60))
    selection.set_selection(session, {first, second})
    align.align(session, "left")
    assert session.undo_label == "Add rectangle"


def test_distribute_needs_three_and_spaces_gaps_evenly():
    session = Session()
    ids = _three(session)
    command = find("object.distribute_x")
    assert command.can_run(session)
    align.distribute(session, "gaps_x")
    boxes = [_box(shape) for shape in all_shapes(session)]
    assert boxes[1][0] - boxes[0][2] == pytest.approx(boxes[2][0] - boxes[1][2])
    selection.set_selection(session, set(ids[:2]))
    assert not command.can_run(session)


def test_align_inside_an_entered_group():
    session = Session()
    _three(session)
    groups.group(session)
    (group,) = all_shapes(session)
    edit_mode.enter(session, group.id)
    selection.set_selection(session, {child.id for child in group.children})
    align.align(session, "top")
    (group,) = all_shapes(session)
    assert [_box(child)[1] for child in group.children] == pytest.approx([0, 0, 0])


def test_unknown_reference_is_refused():
    with pytest.raises(ValueError):
        align.set_align_reference(Session(), "page")
