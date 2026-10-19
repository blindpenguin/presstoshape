from presstoshape.editing.operations._document import add_on_top, delete_selected, insert_copies, with_fresh_ids
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Layer
from presstoshape.models.shapes import CompositeShape, RectShape, Style

S = Style()


def _rect(shape_id: int, x: float = 0) -> RectShape:
    return RectShape(shape_id, x, 0, 10, 10, S)


def _ids(shapes) -> list[int]:
    return [shape.id for shape in shapes]


def _composite_session() -> Session:
    """Layer: [rect 1, composite 10 = [rect 2, rect 3 (subtract), rect 4]], editing the composite."""
    session = Session()
    composite = CompositeShape(10, (_rect(2), _rect(3), _rect(4)), ("add", "subtract", "add"), S)
    session.state.document.layers[0].shapes = [_rect(1), composite]
    session.state.document.next_id = 20
    session.state.edit_path = (10,)
    return session


def test_fresh_ids_come_from_the_document_and_reach_nested_parts():
    session = Session()
    session.state.document.next_id = 50
    inner = CompositeShape(7, (_rect(8), _rect(9)), ("add", "add"), S)
    shapes = [_rect(1, x=5), CompositeShape(6, (_rect(2), inner), ("add", "subtract"), S)]
    copies = with_fresh_ids(session.state, shapes)
    assert copies[0] == RectShape(50, 5, 0, 10, 10, S)
    assert copies[1].id == 51
    assert _ids(copies[1].parts) == [52, 53]
    assert _ids(copies[1].parts[1].parts) == [54, 55]
    assert copies[1].modes == ("add", "subtract")
    assert session.state.document.next_id == 56


def test_add_on_top_goes_to_the_active_layer_even_when_hidden():
    session = Session()
    state = session.state
    state.document.layers = [Layer("A", shapes=[_rect(1)]), Layer("B", visible=False, shapes=[_rect(2)])]
    state.selected_layer_index = 1
    add_on_top(state, [_rect(5), _rect(6)])
    assert _ids(state.document.layers[1].shapes) == [2, 5, 6]
    assert _ids(state.document.layers[0].shapes) == [1]


def test_add_on_top_in_a_composite_uses_the_new_part_mode():
    session = _composite_session()
    session.state.new_part_mode = "intersect"
    add_on_top(session.state, [_rect(21)])
    composite = session.state.document.layers[0].shapes[1]
    assert _ids(composite.parts) == [2, 3, 4, 21]
    assert composite.modes == ("add", "subtract", "add", "intersect")


def test_copies_go_above_the_topmost_original_of_each_layer():
    session = Session()
    state = session.state
    state.document.layers = [
        Layer("A", shapes=[_rect(1), _rect(2), _rect(3), _rect(4)]),
        Layer("B", shapes=[_rect(5), _rect(6)]),
    ]
    insert_copies(state, {1: _rect(11), 3: _rect(13), 5: _rect(15)})
    assert _ids(state.document.layers[0].shapes) == [1, 2, 3, 11, 13, 4]
    assert _ids(state.document.layers[1].shapes) == [5, 15, 6]


def test_copies_in_a_composite_take_the_given_modes():
    session = _composite_session()
    insert_copies(session.state, {3: _rect(23)}, modes={23: "subtract"})
    composite = session.state.document.layers[0].shapes[1]
    assert _ids(composite.parts) == [2, 3, 23, 4]
    assert composite.modes == ("add", "subtract", "subtract", "add")


def test_deleting_the_last_parts_removes_the_composite_and_leaves_edit_mode():
    session = _composite_session()
    session.state.selection = {2, 3, 4}
    delete_selected(session.state)
    assert _ids(session.state.document.layers[0].shapes) == [1]
    assert session.state.edit_path == ()
    assert session.state.selection == set()
