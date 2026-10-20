import re

import pytest

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import composites, documents, edit_mode, layers, paths, selection, shapes, style
from presstoshape.editing.session import Session
from presstoshape.geometry import booleans, transforms
from presstoshape.models.shapes import CompositeShape, PathShape
from tests.helpers import all_shapes


def _area(shape) -> float:
    return booleans._to_skia(transforms.outline(shape)).area


def _two_squares(session):
    keep = shapes.add_rectangle(session, (100, 100), (110, 110))
    bottom = shapes.add_rectangle(session, (0, 0), (10, 10))
    top = shapes.add_rectangle(session, (5, 5), (15, 15))
    selection.set_selection(session, {bottom, top})
    return keep, bottom, top


def _composite_session(mode="subtract"):
    session = Session()
    keep, bottom, top = _two_squares(session)
    composites.make_composite(session, mode)
    (composite_id,) = session.state.selection
    return session, keep, bottom, top, composite_id


@pytest.mark.parametrize("mode, area", [("add", 175), ("subtract", 75), ("intersect", 25), ("exclude", 150)])
def test_make_composite_in_each_mode(mode, area):
    session, keep, bottom, top, composite_id = _composite_session(mode)
    current = all_shapes(session)
    assert [shape.id for shape in current] == [keep, composite_id]
    composite = current[1]
    assert isinstance(composite, CompositeShape)
    assert [part.id for part in composite.parts] == [bottom, top]
    assert composite.modes == ("add", mode)
    assert composite.style == composite.parts[0].style
    assert _area(composite) == pytest.approx(area)
    assert session.undo_label == "Make Composite"


def test_text_is_left_out_and_two_outlines_are_needed():
    session = Session()
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    text = shapes.add_text(session, (0, 0), "x")
    selection.set_selection(session, {rect, text})
    composites.make_composite(session)
    assert len(all_shapes(session)) == 2 and not any(isinstance(s, CompositeShape) for s in all_shapes(session))


def test_composite_style_changes_without_touching_parts():
    session, _, _, _, composite_id = _composite_session()
    style.set_fill(session, "#00ff00")
    composite = queries.find_shape(session.state, composite_id)
    assert composite.style.fill == "#00ff00"
    assert all(part.style.fill != "#00ff00" for part in composite.parts)


def test_moving_a_composite_moves_its_parts():
    session, _, bottom, _, composite_id = _composite_session()
    selection.move_selection(session, 10, 0)
    assert queries.find_shape(session.state, bottom).x == 10


def test_enter_and_leave_are_not_undo_steps():
    session, _, bottom, top, composite_id = _composite_session()
    depth = session.undo_count
    edit_mode.enter(session, composite_id)
    assert session.state.edit_path == (composite_id,)
    assert session.state.selection == set()
    assert {shape.id for shape in queries.pickable_shapes(session.state)} == {bottom, top}
    edit_mode.leave(session)
    assert session.state.edit_path == () and session.state.selection == {composite_id}
    assert session.undo_count == depth


def test_set_part_mode_skips_the_base():
    session, _, bottom, top, composite_id = _composite_session("add")
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {bottom, top})
    composites.set_part_mode(session, "intersect")
    composite = queries.find_shape(session.state, composite_id)
    assert composite.modes == ("add", "intersect")
    assert session.undo_label == "Change mode"
    assert _area(composite) == pytest.approx(25)


def test_make_composite_inside_edit_mode_nests_and_takes_the_bottom_mode():
    session, _, bottom, top, composite_id = _composite_session("subtract")
    edit_mode.enter(session, composite_id)
    extra = shapes.add_rectangle(session, (20, 20), (30, 30))
    composite = queries.find_shape(session.state, composite_id)
    assert composite.modes[-1] == "add"
    selection.set_selection(session, {top, extra})
    composites.make_composite(session, "add")
    (nested_id,) = session.state.selection
    composite = queries.find_shape(session.state, composite_id)
    assert [part.id for part in composite.parts] == [bottom, nested_id]
    # The nested Composite took `top`'s place and its subtract mode.
    assert composite.modes[1] == "subtract"


def test_release_puts_parts_back_in_place():
    session, keep, bottom, top, composite_id = _composite_session()
    composites.release_composite(session)
    assert [shape.id for shape in all_shapes(session)] == [keep, bottom, top]
    assert session.state.selection == {bottom, top}
    assert session.undo_label == "Release Composite"


def test_flatten_and_object_to_path_bake_the_result():
    session, _, _, _, composite_id = _composite_session()
    composites.flatten_composite(session)
    flat = queries.find_shape(session.state, composite_id)
    assert isinstance(flat, PathShape) and _area(flat) == pytest.approx(75)
    session.undo()
    paths.object_to_path(session)
    assert isinstance(queries.find_shape(session.state, composite_id), PathShape)


def test_deleting_the_last_part_deletes_the_composite_and_leaves():
    session, keep, bottom, top, composite_id = _composite_session()
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {bottom})
    selection.delete_selection(session)
    composite = queries.find_shape(session.state, composite_id)
    assert [part.id for part in composite.parts] == [top]
    selection.set_selection(session, {top})
    selection.delete_selection(session)
    assert queries.find_shape(session.state, composite_id) is None
    assert session.state.edit_path == ()
    session.undo()
    assert queries.find_shape(session.state, composite_id) is not None


def test_undo_past_creation_leaves_edit_mode():
    session, _, bottom, top, composite_id = _composite_session()
    edit_mode.enter(session, composite_id)
    session.undo()
    assert session.state.edit_path == ()
    assert queries.find_shape(session.state, composite_id) is None


def test_layer_changes_leave_edit_mode():
    session, _, _, _, composite_id = _composite_session()
    edit_mode.enter(session, composite_id)
    layers.add_layer(session)
    layers.select_layer(session, 0)
    assert session.state.edit_path == ()


def test_nested_enter_and_leave_levels():
    session, _, bottom, top, composite_id = _composite_session()
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session)
    (nested_id,) = session.state.selection
    edit_mode.enter(session, nested_id)
    assert session.state.edit_path == (composite_id, nested_id)
    assert containers.edited_composite(session.state).id == nested_id
    edit_mode.leave(session, levels=2)
    assert session.state.edit_path == () and session.state.selection == {composite_id}


def test_new_part_mode_is_used_for_drawn_parts():
    session, _, _, _, composite_id = _composite_session()
    edit_mode.enter(session, composite_id)
    composites.set_new_part_mode(session, "exclude")
    part = shapes.add_ellipse(session, (0, 0), (20, 20))
    composite = queries.find_shape(session.state, composite_id)
    assert composite.parts[-1].id == part and composite.modes[-1] == "exclude"


def test_save_and_open_keep_the_composite(tmp_path):
    session, _, bottom, top, composite_id = _composite_session()
    target = str(tmp_path / "composite.svg")
    assert documents.save_file(session, target)
    reopened = Session()
    assert documents.open_file(reopened, target)
    composite = all_shapes(reopened)[-1]
    assert isinstance(composite, CompositeShape) and composite.modes == ("add", "subtract")
    assert "edited in another program" not in reopened.state.status_message


def test_opening_an_edited_composite_says_so(tmp_path):
    session, *_ = _composite_session()
    target = tmp_path / "composite.svg"
    documents.save_file(session, str(target))
    text = target.read_text(encoding="utf-8")
    target.write_text(re.sub(r'd="M[^"]*"', 'd="M 0 0 L 50 0 L 50 50 Z"', text, count=1), encoding="utf-8")
    reopened = Session()
    documents.open_file(reopened, str(target))
    assert isinstance(all_shapes(reopened)[-1], PathShape)
    assert "1 import note" in reopened.state.status_message
    assert "edited in another program" in reopened.state.import_notes[0]
