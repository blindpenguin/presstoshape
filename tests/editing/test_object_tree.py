from presstoshape.editing.object_tree import Location, inherited_flags, locate, object_label, object_type
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Layer
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GroupShape,
    PathShape,
    RectShape,
    Style,
    TextShape,
)

S = Style()


def _rect(shape_id: int, **flags) -> RectShape:
    return RectShape(shape_id, 0, 0, 10, 10, S, **flags)


def test_types_and_labels():
    shapes = [
        _rect(1),
        EllipseShape(2, 0, 0, 5, 5, S),
        PathShape(3, (), S),
        TextShape(4, 0, 0, "Hello", 12, S),
        GroupShape(5, ()),
        CompositeShape(6, (), (), S),
    ]
    assert [object_type(shape) for shape in shapes] == ["rect", "ellipse", "path", "text", "group", "composite"]
    assert [object_label(shape) for shape in shapes] == ["Rectangle", "Ellipse", "Path", "Hello", "Group", "Composite"]


def test_text_labels_use_the_first_line_shortened():
    assert object_label(TextShape(1, 0, 0, "  First line\nsecond", 12, S)) == "First line"
    long_label = object_label(TextShape(1, 0, 0, "x" * 50, 12, S))
    assert len(long_label) == 30 and long_label.endswith("…")
    assert object_label(TextShape(1, 0, 0, "   ", 12, S)) == "Text"


def _state():
    session = Session()
    composite = CompositeShape(20, (_rect(3), _rect(4)), ("add", "subtract"), S)
    group = GroupShape(10, (_rect(2), composite))
    session.state.document.layers = [Layer("Bottom", True, [_rect(1)]), Layer("Top", True, [group])]
    return session


def test_locate_top_level_group_child_and_nested_part():
    state = _state().state
    assert locate(state, 1) == Location(0, ())
    assert locate(state, 10) == Location(1, ())
    assert locate(state, 2) == Location(1, (10,))
    assert locate(state, 4) == Location(1, (10, 20))
    assert locate(state, 99) is None


def test_inherited_flags_come_from_the_layer_and_containers():
    session = _state()
    state = session.state
    assert inherited_flags(state, locate(state, 4)) == (False, False)
    state.document.layers[1].visible = False
    assert inherited_flags(state, locate(state, 4)) == (True, False)
    state.document.layers[1].visible = True
    group = state.document.layers[1].shapes[0]
    from dataclasses import replace

    state.document.layers[1].shapes = [replace(group, locked=True)]
    assert inherited_flags(state, locate(state, 4)) == (False, True)
    assert inherited_flags(state, locate(state, 10)) == (False, False)
    state.document.layers[0].locked = True
    assert inherited_flags(state, locate(state, 1)) == (False, True)
