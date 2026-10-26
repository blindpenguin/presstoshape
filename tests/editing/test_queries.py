from presstoshape.editing import queries
from presstoshape.models.app_state import AppState, Document, Layer
from presstoshape.models.shapes import CompositeShape, GroupShape, RectShape, Style


def test_find_shapes_reaches_group_children_parts_and_locked_layers():
    inner = RectShape(2, 0, 0, 1, 1, Style())
    part = RectShape(4, 0, 0, 1, 1, Style())
    composite = CompositeShape(5, (part, RectShape(6, 0, 0, 1, 1, Style())), ("add", "add"), Style())
    state = AppState(
        document=Document(
            layers=[
                Layer("A", shapes=[GroupShape(1, (inner,)), composite]),
                Layer("B", locked=True, shapes=[RectShape(3, 0, 0, 1, 1, Style(), locked=True)]),
            ],
            next_id=7,
        )
    )
    found = queries.find_shapes(state, {2, 3, 4, 99})
    assert set(found) == {2, 3, 4}
    assert found[2] is inner and found[4] is part
    assert queries.find_shapes(state, set()) == {}
