from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import selection, shapes, style
from presstoshape.editing.session import Session
from presstoshape.models.shapes import CompositeShape, RectShape, Style

S = Style()


def _nested_session() -> tuple[Session, int, int]:
    """Layer: [loose rect 1, outer composite 10 = [rect 2, inner composite 20 = [rect 3, rect 4 (subtract)]]]."""
    session = Session()
    inner = CompositeShape(20, (RectShape(3, 0, 0, 10, 10, S), RectShape(4, 5, 5, 10, 10, S)), ("add", "subtract"), S)
    outer = CompositeShape(10, (RectShape(2, 50, 50, 10, 10, S), inner), ("add", "add"), S)
    session.state.document.layers[0].shapes = [RectShape(1, 100, 100, 5, 5, S), outer]
    session.state.document.next_id = 30
    return session, 10, 20


def _outer(session) -> CompositeShape:
    return session.state.document.layers[0].shapes[1]


def test_outside_edit_mode_everything_is_as_before():
    session, _, _ = _nested_session()
    assert not containers.editing(session.state)
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [1, 10]
    assert len(containers.container_lists(session.state)) == 1


def test_depth_one_and_two_pickables_are_the_parts():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id,)
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [2, 20]
    session.state.edit_path = (outer_id, inner_id)
    assert [shape.id for shape in queries.pickable_shapes(session.state)] == [3, 4]
    assert containers.edited_composite(session.state).id == inner_id


def test_change_at_depth_two_rebuilds_the_chain_and_the_layer():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id, inner_id)
    containers.change_container(
        session.state, lambda parts: [replace(part, x=part.x + 1) if part.id == 3 else part for part in parts]
    )
    outer = _outer(session)
    assert outer.id == outer_id
    inner = outer.parts[1]
    assert inner.parts[0].x == 1 and inner.modes == ("add", "subtract")


def test_modes_stay_with_their_part_when_the_order_changes():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id, inner_id)
    containers.change_container(session.state, lambda parts: list(reversed(parts)))
    inner = _outer(session).parts[1]
    assert [part.id for part in inner.parts] == [4, 3]
    assert inner.modes == ("subtract", "add")


def test_new_parts_get_the_new_part_mode_and_explicit_modes_win():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id, inner_id)
    session.state.new_part_mode = "intersect"
    containers.change_container(session.state, lambda parts: [*parts, RectShape(5, 0, 0, 1, 1, S)])
    containers.change_container(session.state, lambda parts: [*parts, RectShape(6, 0, 0, 1, 1, S)], {6: "exclude"})
    assert _outer(session).parts[1].modes == ("add", "subtract", "intersect", "exclude")


def test_drawing_in_edit_mode_adds_a_part():
    session, outer_id, _ = _nested_session()
    session.state.edit_path = (outer_id,)
    session.state.new_part_mode = "subtract"
    new_id = shapes.add_rectangle(session, (0, 0), (20, 20))
    outer = _outer(session)
    assert outer.parts[-1].id == new_id and outer.modes[-1] == "subtract"
    assert session.state.selection == {new_id}
    assert len(session.state.document.layers[0].shapes) == 2


def test_existing_operations_work_on_parts():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id, inner_id)
    selection.set_selection(session, {3})
    style.set_fill(session, "#00ff00")
    selection.move_selection(session, 5, 0)
    part = _outer(session).parts[1].parts[0]
    assert part.style.fill == "#00ff00" and part.x == 5
    assert session.undo_label == "Move 1 object"


def test_find_shape_reaches_nested_parts():
    session, _, _ = _nested_session()
    assert queries.find_shape(session.state, 4).x == 5


def test_undo_trims_edit_path_and_keeps_part_selection():
    session, outer_id, inner_id = _nested_session()
    session.state.edit_path = (outer_id, inner_id)
    selection.set_selection(session, {3})
    selection.move_selection(session, 5, 0)
    session.undo()
    assert session.state.edit_path == (outer_id, inner_id)
    assert session.state.selection == {3}
    # A Composite that no longer exists is left.
    session.state.document.layers[0].shapes = [RectShape(1, 0, 0, 5, 5, S)]
    session.state.edit_path = (outer_id, inner_id)
    assert containers.valid_edit_path(session.state) == ()


def test_stale_edit_path_prefix_is_kept():
    session, outer_id, _ = _nested_session()
    session.state.edit_path = (outer_id, 999)
    assert containers.valid_edit_path(session.state) == (outer_id,)
