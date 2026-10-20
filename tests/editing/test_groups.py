import pytest

from presstoshape.editing import containers
from presstoshape.editing.operations import edit_mode, groups, selection, style, transform
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Layer
from presstoshape.models.shapes import CompositeShape, GroupShape, RectShape, Style, TextShape
from presstoshape.render.paths import PathCache

RED = Style(fill="#ff0000", stroke=None)


def _rect(shape_id: int, x: float = 0, style: Style = RED) -> RectShape:
    return RectShape(shape_id, x, 0, 10, 10, style)


def _session(*shapes) -> Session:
    session = Session()
    session.state.document.layers[0].shapes = list(shapes)
    session.state.document.next_id = 100
    return session


def _ids(shapes) -> list[int]:
    return [shape.id for shape in shapes]


def _layer(session, index: int = 0) -> list:
    return session.state.document.layers[index].shapes


def test_group_keeps_order_and_takes_the_place_of_the_top_most_shape():
    session = _session(_rect(1), _rect(2), _rect(3), _rect(4))
    selection.set_selection(session, {1, 3})
    groups.group(session)
    assert _ids(_layer(session)) == [2, 100, 4]
    assert _ids(_layer(session)[1].children) == [1, 3]
    assert session.state.selection == {100}
    assert session.undo_label == "Group"
    session.undo()
    assert _ids(_layer(session)) == [1, 2, 3, 4]


def test_group_across_layers_lands_in_the_layer_of_the_top_most_shape():
    session = _session(_rect(1))
    session.state.document.layers.append(Layer("Top", True, [_rect(2), _rect(3)]))
    selection.set_selection(session, {1, 2})
    groups.group(session)
    assert _ids(_layer(session, 0)) == []
    assert _ids(_layer(session, 1)) == [100, 3]


def test_a_single_shape_can_be_grouped():
    session = _session(_rect(1))
    selection.set_selection(session, {1})
    groups.group(session)
    assert isinstance(_layer(session)[0], GroupShape)


def test_group_is_disabled_without_selection_and_inside_a_composite():
    command = find("object.group")
    session = _session(CompositeShape(1, (_rect(2), _rect(3)), ("add", "add"), RED))
    assert not command.can_run(session)
    edit_mode.enter(session, 1)
    selection.set_selection(session, {2})
    assert not command.can_run(session)
    groups.group(session)
    assert not session.can_undo


def test_grouping_inside_a_group_nests():
    session = _session(GroupShape(1, (_rect(2), _rect(3), _rect(4))))
    edit_mode.enter(session, 1)
    selection.set_selection(session, {2, 3})
    groups.group(session)
    outer = _layer(session)[0]
    assert _ids(outer.children) == [100, 4]
    assert containers.valid_edit_path(session.state) == (1,)


def test_ungroup_puts_the_shapes_back_in_place_and_selects_them():
    session = _session(_rect(1), GroupShape(2, (_rect(3), _rect(4))), _rect(5))
    selection.set_selection(session, {2})
    assert find("object.ungroup").can_run(session)
    groups.ungroup(session)
    assert _ids(_layer(session)) == [1, 3, 4, 5]
    assert session.state.selection == {3, 4}
    assert session.undo_label == "Ungroup"


def test_ungroup_moves_the_group_opacity_into_its_shapes():
    composite = CompositeShape(5, (_rect(6), _rect(7)), ("add", "add"), RED)
    inner = GroupShape(4, (_rect(8),), opacity=0.5)
    session = _session(GroupShape(1, (_rect(2, style=Style(opacity=0.8)), inner, composite), opacity=0.5))
    selection.set_selection(session, {1})
    groups.ungroup(session)
    rect, nested, released_composite = _layer(session)
    assert rect.style.opacity == pytest.approx(0.4)
    assert nested.opacity == pytest.approx(0.25) and nested.children[0].style.opacity == 1
    assert released_composite.style.opacity == pytest.approx(0.5)
    assert released_composite.parts[0].style.opacity == 1


def test_ungroup_needs_a_group():
    session = _session(_rect(1))
    selection.set_selection(session, {1})
    assert not find("object.ungroup").can_run(session)


def test_group_opacity_is_the_groups_and_other_fields_reach_every_shape():
    text = TextShape(4, 0, 30, "Hi", 12, RED)
    session = _session(GroupShape(1, (_rect(2), GroupShape(3, (text,)))))
    selection.set_selection(session, {1})
    style.set_style(session, opacity=0.5)
    group = _layer(session)[0]
    assert group.opacity == 0.5 and group.children[0].style.opacity == 1
    style.set_style(session, fill="#00ff00")
    group = _layer(session)[0]
    assert group.children[0].style.fill == "#00ff00"
    assert group.children[1].children[0].style.fill == "#00ff00"
    assert style.display_style(group) == Style(fill="#00ff00", stroke=None, opacity=0.5)


def test_display_style_of_an_empty_nested_group_is_the_default():
    assert style.display_style(GroupShape(1, (GroupShape(2, ()),), opacity=0.3)) == Style(opacity=0.3)


def test_set_bounds_moves_and_scales_a_group():
    session = _session(GroupShape(1, (_rect(2), _rect(3, 30))))
    transform.set_bounds(session, 1, "x", 50)
    transform.set_bounds(session, 1, "width", 80)
    group = _layer(session)[0]
    box = PathCache().geometry_bounds(group)
    assert (box.left(), box.top(), box.width(), box.height()) == pytest.approx((50, 0, 80, 10))
    assert session.undo_label == "Change width"
    with pytest.raises(ValueError):
        transform.set_bounds(session, 1, "depth", 1)
