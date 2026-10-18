import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import arrange, composites, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.geometry import booleans, transforms
from tests.helpers import all_shapes


def _four(session):
    return [shapes.add_rectangle(session, (i * 20, 0), (i * 20 + 10, 10)) for i in range(4)]


@pytest.mark.parametrize(
    "command, picked, order",
    [
        (arrange.raise_selection, [0, 1], [2, 0, 1, 3]),
        (arrange.lower_selection, [2, 3], [0, 2, 3, 1]),
        (arrange.raise_to_top, [0, 2], [1, 3, 0, 2]),
        (arrange.lower_to_bottom, [1, 3], [1, 3, 0, 2]),
    ],
)
def test_arrange_keeps_selected_together_in_order(command, picked, order):
    session = Session()
    ids = _four(session)
    selection.set_selection(session, {ids[i] for i in picked})
    command(session)
    assert [shape.id for shape in all_shapes(session)] == [ids[i] for i in order]


def test_no_op_at_the_end_records_no_undo_step():
    session = Session()
    ids = _four(session)
    selection.set_selection(session, {ids[3]})
    depth = session.undo_count
    arrange.raise_selection(session)
    arrange.raise_to_top(session)
    assert session.undo_count == depth


def test_reordering_parts_changes_the_composite_result():
    session = Session()
    big = shapes.add_rectangle(session, (0, 0), (10, 10))
    cutter = shapes.add_rectangle(session, (5, 0), (15, 10))
    patch = shapes.add_rectangle(session, (5, 0), (10, 10))
    selection.set_selection(session, {big, cutter, patch})
    composites.make_composite(session)
    (composite_id,) = session.state.selection
    composites.enter(session, composite_id)
    selection.set_selection(session, {cutter})
    composites.set_part_mode(session, "subtract")
    before = booleans._to_skia(transforms.outline(queries.find_shape(session.state, composite_id))).area
    # Cutting last removes the patch again.
    arrange.raise_to_top(session)
    after = booleans._to_skia(transforms.outline(queries.find_shape(session.state, composite_id))).area
    assert before == pytest.approx(100) and after == pytest.approx(50)
    assert session.undo_label == "Raise to top"
