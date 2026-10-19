import json

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import clipboard, composites, layers, selection, shapes
from presstoshape.editing.operations.clipboard import (
    copy_selection,
    cut_selection,
    duplicate_and_move,
    duplicate_selection,
    paste,
)
from presstoshape.editing.session import Session
from presstoshape.formats.clipboard import encode_shapes
from presstoshape.models.shapes import CompositeShape, PathShape, RectShape, Style, TextShape
from tests.helpers import all_shapes


def _ids(shape_list) -> list[int]:
    return [shape.id for shape in shape_list]


def _all_ids(shape_list) -> list[int]:
    ids = []
    for shape in shape_list:
        ids.append(shape.id)
        if isinstance(shape, CompositeShape):
            ids.extend(_all_ids(shape.parts))
    return ids


def _three_rects() -> tuple[Session, int, int, int]:
    session = Session()
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (20, 0), (30, 10))
    third = shapes.add_rectangle(session, (40, 0), (50, 10))
    return session, first, second, third


def _composite_session() -> tuple[Session, int, int, int]:
    session = Session()
    bottom = shapes.add_rectangle(session, (0, 0), (10, 10))
    top = shapes.add_rectangle(session, (5, 5), (15, 15))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session, "subtract")
    (composite_id,) = session.state.selection
    composites.enter(session, composite_id)
    return session, composite_id, bottom, top


# --- copy and cut ---------------------------------------------------------------------------


def test_copy_has_no_side_effects_and_holds_the_selection_in_paint_order():
    session, first, _, third = _three_rects()
    selection.set_selection(session, {third, first})
    before = (list(all_shapes(session)), session.undo_label, session.state.dirty)
    session.state.dirty = False
    content = copy_selection(session)
    assert (all_shapes(session), session.undo_label) == (before[0], before[1])
    assert not session.state.dirty
    assert session.state.selection == {first, third}
    assert [shape["id"] for shape in json.loads(content.native)["shapes"]] == [first, third]
    assert content.svg.startswith("<?xml") and "viewBox" in content.svg
    assert session.state.status_message == "Copied 2 object(s)"


def test_copy_without_selection_gives_nothing():
    session, *_ = _three_rects()
    selection.set_selection(session, set())
    assert copy_selection(session) is None
    assert cut_selection(session) is None


def test_cut_removes_in_one_undo_step():
    session, first, second, _ = _three_rects()
    selection.set_selection(session, {second})
    content = cut_selection(session)
    assert content is not None
    assert second not in _ids(all_shapes(session))
    assert session.undo_label == "Cut"
    session.undo()
    assert second in _ids(all_shapes(session))


def test_cutting_all_parts_closes_the_composite():
    session, composite_id, bottom, top = _composite_session()
    selection.set_selection(session, {bottom, top})
    cut_selection(session)
    assert composite_id not in _ids(all_shapes(session))
    assert not containers.editing(session.state)


# --- paste ------------------------------------------------------------------------------------


def test_paste_centers_on_the_point_on_top_and_selects():
    session, first, second, _ = _three_rects()
    selection.set_selection(session, {first, second})
    content = copy_selection(session)
    assert paste(session, content.native, content.svg, (100, 100))
    pasted = all_shapes(session)[-2:]
    assert session.state.selection == set(_ids(pasted))
    assert [(shape.x, shape.y) for shape in pasted] == [(85.0, 95.0), (105.0, 95.0)]
    assert session.undo_label == "Paste"
    assert session.state.dirty


def test_paste_in_place_keeps_coordinates():
    session, first, *_ = _three_rects()
    selection.set_selection(session, {first})
    content = copy_selection(session)
    paste(session, content.native, content.svg, None)
    pasted = all_shapes(session)[-1]
    assert pasted.id != first and (pasted.x, pasted.y) == (0, 0)
    assert session.undo_label == "Paste in Place"


def test_repeated_paste_never_reuses_ids_even_inside_composites():
    session, composite_id, *_ = _composite_session()
    composites.leave_all(session.state)
    selection.set_selection(session, {composite_id})
    content = copy_selection(session)
    paste(session, content.native, None, None)
    paste(session, content.native, None, None)
    ids = _all_ids(all_shapes(session))
    assert len(ids) == len(set(ids)) == 9
    assert max(ids) < session.state.document.next_id


def test_native_data_wins_over_svg():
    session = Session()
    native = encode_shapes([RectShape(1, 0, 0, 5, 5, Style())])
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><circle r="3"/></svg>'
    paste(session, native, svg, None)
    assert isinstance(all_shapes(session)[0], RectShape)


def test_svg_is_used_when_native_data_is_broken_or_from_another_version():
    session = Session()
    other = json.loads(encode_shapes([RectShape(1, 0, 0, 5, 5, Style())]))
    other["version"] += 1
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="100 100 10 10"><circle cx="105" cy="105" r="3"/></svg>'
    for native in (b"garbage", json.dumps(other).encode()):
        assert paste(session, native, svg, None)
    assert [(shape.cx, shape.cy) for shape in all_shapes(session)] == [(105, 105), (105, 105)]


def test_foreign_svg_layers_and_groups_paste_flat_in_order():
    session = Session()
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape">'
        '<g inkscape:groupmode="layer"><rect width="1" height="1"/></g>'
        '<g inkscape:groupmode="layer"><g><circle r="2"/><path d="M0 0 L5 5"/></g></g></svg>'
    )
    paste(session, None, svg, (0, 0))
    assert [type(shape).__name__ for shape in all_shapes(session)] == ["RectShape", "EllipseShape", "PathShape"]
    assert len(session.state.document.layers) == 1


def test_nothing_pasteable_reports_and_records_nothing():
    empty_svg = '<svg xmlns="http://www.w3.org/2000/svg"/>'
    for native, svg in ((None, None), (b"junk", None), (None, "<svg"), (None, "<html/>"), (None, empty_svg)):
        session = Session()
        assert not paste(session, native, svg, (0, 0))
        assert session.state.status_message.startswith("Nothing to paste")
        assert session.undo_label is None
        assert all_shapes(session) == []


def test_paste_into_a_hidden_layer_says_so():
    session = Session()
    layers.set_layer_visible(session, 0, False)
    paste(session, encode_shapes([RectShape(1, 0, 0, 5, 5, Style())]), None, None)
    assert len(session.state.document.layers[0].shapes) == 1
    assert "hidden" in session.state.status_message


def test_paste_into_a_composite_uses_the_new_part_mode_and_turns_text_into_paths():
    session, composite_id, bottom, top = _composite_session()
    composites.set_new_part_mode(session, "intersect")
    native = encode_shapes([TextShape(1, 0, 0, "A", 20, Style())])
    paste(session, native, None, None)
    composite = containers.edited_composite(session.state)
    assert composite.id == composite_id
    assert isinstance(composite.parts[-1], PathShape)
    assert composite.modes[-1] == "intersect"
    assert "text became a path" in session.state.status_message


# --- duplicate --------------------------------------------------------------------------------


def test_duplicate_goes_right_above_the_topmost_selected_in_order():
    session, first, second, third = _three_rects()
    selection.set_selection(session, {first, second})
    duplicate_selection(session)
    current = all_shapes(session)
    copies = current[2:4]
    assert _ids(current[:2]) == [first, second] and current[4].id == third
    assert [(shape.x, shape.y) for shape in copies] == [(0, 0), (20, 0)]
    assert session.state.selection == set(_ids(copies))
    assert session.undo_label == "Duplicate"


def test_duplicate_keeps_part_modes():
    session, composite_id, bottom, top = _composite_session()
    selection.set_selection(session, {top})
    duplicate_selection(session)
    composite = containers.edited_composite(session.state)
    assert composite.modes == ("add", "subtract", "subtract")


def test_duplicate_and_move_is_one_step_and_leaves_originals():
    session, first, *_ = _three_rects()
    selection.set_selection(session, {first})
    duplicate_and_move(session, 5, 7)
    original, copy = all_shapes(session)[0], all_shapes(session)[1]
    assert (original.x, original.y) == (0, 0)
    assert (copy.x, copy.y) == (5, 7) and session.state.selection == {copy.id}
    session.undo()
    assert len(all_shapes(session)) == 3


def test_duplicate_is_registered_and_needs_a_selection():
    from presstoshape.editing import registry

    session = Session()
    assert not registry.find("edit.duplicate").can_run(session)
    assert clipboard.duplicate_selection is registry.find("edit.duplicate").run
    assert queries.selected_shapes(session.state) == []
