import pytest

from presstoshape.editing import containers
from presstoshape.editing.operations import booleans, groups, masks, selection, style
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Layer
from presstoshape.models.shapes import (
    CompositeShape,
    GroupShape,
    Masking,
    RectShape,
    Style,
    content_children,
    mask_children,
)

RED = Style(fill="#ff0000", stroke=None)
FILLED_MASK = Style(fill="#000000", stroke=None)


def _rect(shape_id: int, x: float = 0, shape_style: Style = RED, **fields) -> RectShape:
    return RectShape(shape_id, x, 0, 10, 10, shape_style, **fields)


def _session(*shapes) -> Session:
    session = Session()
    session.state.document.layers[0].shapes = list(shapes)
    session.state.document.next_id = 100
    return session


def _layer(session, index: int = 0) -> list:
    return session.state.document.layers[index].shapes


def _ids(shapes) -> list[int]:
    return [shape.id for shape in shapes]


def _masked_session(mask_type="clip", **fields) -> Session:
    group = GroupShape(
        50,
        (_rect(1), _rect(2), _rect(3, shape_style=FILLED_MASK)),
        opacity=fields.pop("opacity", 1.0),
        masking=Masking(mask_type, (3,), **fields),
    )
    return _session(group, _rect(4))


# --- make ------------------------------------------------------------------------------------------


def test_make_clip_uses_the_top_most_selected_shape_as_the_mask():
    session = _session(_rect(1), _rect(2), _rect(3), _rect(4))
    selection.set_selection(session, {1, 3, 4})
    masks.make_clip(session)
    assert _ids(_layer(session)) == [2, 100]
    group = _layer(session)[1]
    assert (group.masking.type, group.masking.mask_ids, _ids(group.children)) == ("clip", (4,), [1, 3, 4])
    assert session.state.selection == {100}
    assert session.undo_label == "Make Clipping Mask"
    assert session.state.status_message.startswith("Made a clipping mask")


def test_make_opacity_mask_is_luminance():
    session = _session(_rect(1), _rect(2))
    selection.set_selection(session, {1, 2})
    masks.make_opacity_mask(session)
    assert _layer(session)[0].masking == Masking("luminance", (2,))
    assert session.undo_label == "Make Opacity Mask"


def test_make_can_be_undone():
    session = _session(_rect(1), _rect(2))
    selection.set_selection(session, {1, 2})
    masks.make_clip(session)
    session.undo()
    assert _ids(_layer(session)) == [1, 2]


@pytest.mark.parametrize("selected", [set(), {1}])
def test_make_needs_two_objects(selected):
    session = _session(_rect(1), _rect(2))
    selection.set_selection(session, selected)
    assert not find("object.clip.make").can_run(session)
    assert not find("object.mask.make").can_run(session)
    masks.make_clip(session)
    assert _ids(_layer(session)) == [1, 2]
    assert "at least" in session.state.status_message or "Select" in session.state.status_message


def test_make_refuses_objects_of_different_layers():
    session = _session(_rect(1))
    session.state.document.layers.append(Layer("Two", True, [_rect(2)]))
    selection.set_selection(session, {1, 2})
    assert not find("object.clip.make").can_run(session)
    masks.make_clip(session)
    assert [_ids(layer.shapes) for layer in session.state.document.layers] == [[1], [2]]
    assert "same layer" in session.state.status_message


def test_make_refuses_inside_a_composite():
    composite = CompositeShape(9, (_rect(1), _rect(2)), ("add", "add"), RED)
    session = _session(composite)
    session.state.edit_path = (9,)
    selection.set_selection(session, {1, 2})
    assert not find("object.clip.make").can_run(session)
    masks.make_clip(session)
    assert _ids(composite.parts) == [1, 2] and "Composite" in session.state.status_message


def test_make_inside_a_group_nests_the_new_mask():
    session = _session(GroupShape(9, (_rect(1), _rect(2), _rect(3))))
    session.state.edit_path = (9,)
    selection.set_selection(session, {2, 3})
    masks.make_clip(session)
    (group,) = _layer(session)
    assert _ids(group.children) == [1, 100]
    assert group.children[1].masking.mask_ids == (3,)


def test_make_nests_masked_groups_instead_of_flattening_them():
    session = _masked_session()
    selection.set_selection(session, {50, 4})
    masks.make_opacity_mask(session)
    (outer,) = _layer(session)
    assert outer.masking.type == "luminance" and outer.masking.mask_ids == (4,)
    assert outer.children[0].masking.type == "clip"


# --- release ---------------------------------------------------------------------------------------


def test_release_clip_keeps_everything_and_outlines_the_mask_object():
    session = _masked_session()
    selection.set_selection(session, {50})
    masks.release_clip(session)
    assert _ids(_layer(session)) == [1, 2, 3, 4]
    released = _layer(session)[2]
    assert (released.style.fill, released.style.stroke, released.style.stroke_width) == (None, "#18181b", 1.0)
    assert session.state.selection == {1, 2, 3}
    assert session.undo_label == "Release Clipping Mask"


def test_release_opacity_mask_hides_the_mask_objects_and_selects_the_content():
    session = _masked_session("luminance")
    selection.set_selection(session, {50})
    masks.release_opacity_mask(session)
    assert [shape.hidden for shape in _layer(session)] == [False, False, True, False]
    assert session.state.selection == {1, 2}


def test_release_only_takes_the_matching_kind():
    session = _masked_session("luminance")
    selection.set_selection(session, {50})
    assert not find("object.clip.release").can_run(session)
    assert find("object.mask.release").can_run(session)
    masks.release_clip(session)
    assert isinstance(_layer(session)[0], GroupShape)


def test_release_hands_the_group_opacity_to_the_shapes():
    session = _masked_session(opacity=0.5)
    selection.set_selection(session, {50})
    masks.release_clip(session)
    assert [shape.style.opacity for shape in _layer(session)[:2]] == [0.5, 0.5]


def test_release_undo_restores_the_mask():
    session = _masked_session()
    selection.set_selection(session, {50})
    masks.release_clip(session)
    session.undo()
    assert _layer(session)[0].masking == Masking("clip", (3,))


def test_ungroup_releases_a_masked_group():
    session = _masked_session()
    selection.set_selection(session, {50})
    groups.ungroup(session)
    assert _ids(_layer(session)) == [1, 2, 3, 4]
    assert _layer(session)[2].style.stroke == "#18181b"


# --- invert and type ----------------------------------------------------------------------------


def test_invert_toggles_and_reports_its_check_state():
    session = _masked_session()
    selection.set_selection(session, {50})
    entry = find("object.mask.invert")
    assert not entry.checked(session)
    masks.invert_mask(session)
    assert _layer(session)[0].masking.inverted and entry.checked(session)
    assert session.undo_label == "Invert Mask"
    masks.invert_mask(session)
    assert not _layer(session)[0].masking.inverted


def test_invert_needs_a_masked_group():
    session = _session(_rect(1))
    selection.set_selection(session, {1})
    assert not find("object.mask.invert").can_run(session)


def test_mask_type_switches_between_luminance_and_alpha():
    session = _masked_session("luminance")
    selection.set_selection(session, {50})
    assert find("object.mask.type_luminance").checked(session)
    masks.mask_type_alpha(session)
    assert _layer(session)[0].masking.type == "alpha" and find("object.mask.type_alpha").checked(session)
    assert session.undo_label == "Mask by Alpha"
    masks.mask_type_luminance(session)
    assert _layer(session)[0].masking.type == "luminance"


def test_mask_type_does_not_apply_to_clipping_masks():
    session = _masked_session("clip")
    selection.set_selection(session, {50})
    assert not find("object.mask.type_alpha").can_run(session)
    masks.mask_type_alpha(session)
    assert _layer(session)[0].masking.type == "clip"


def test_changes_reach_masked_groups_inside_other_groups():
    inner = GroupShape(50, (_rect(1), _rect(2)), masking=Masking("clip", (2,)))
    session = _session(GroupShape(60, (inner,)))
    session.state.edit_path = (60,)
    selection.set_selection(session, {50})
    masks.invert_mask(session)
    assert _layer(session)[0].children[0].masking.inverted


# --- moving between the sides ---------------------------------------------------------------------


def test_add_to_mask_and_move_to_content_while_entered():
    session = _masked_session()
    session.state.edit_path = (50,)
    selection.set_selection(session, {2})
    assert find("object.mask.to_mask").can_run(session) and not find("object.mask.to_content").can_run(session)
    masks.move_to_mask(session)
    group = _layer(session)[0]
    assert group.masking.mask_ids == (2, 3) and _ids(content_children(group)) == [1]
    assert session.undo_label == "Add to Mask"
    selection.set_selection(session, {3})
    masks.move_to_content(session)
    assert _layer(session)[0].masking.mask_ids == (2,)
    assert "content" in session.state.status_message


def test_move_between_sides_needs_an_entered_masked_group():
    session = _masked_session()
    selection.set_selection(session, {50})
    assert not find("object.mask.to_mask").can_run(session)
    assert not find("object.mask.to_content").can_run(session)


# --- the rest of the editor ---------------------------------------------------------------------


def test_deleting_the_mask_object_keeps_the_group_with_an_empty_mask():
    session = _masked_session()
    session.state.edit_path = (50,)
    selection.set_selection(session, {3})
    containers.change_container(session.state, lambda shapes: [s for s in shapes if s.id != 3])
    group = _layer(session)[0]
    assert group.masking == Masking("clip", ()) and _ids(group.children) == [1, 2]


def test_deleting_every_child_removes_the_group():
    session = _masked_session()
    session.state.edit_path = (50,)
    containers.change_container(session.state, lambda shapes: [])
    assert _ids(_layer(session)) == [4] and session.state.edit_path == ()


def test_restyling_a_masked_group_leaves_the_mask_objects_alone():
    session = _masked_session()
    selection.set_selection(session, {50})
    restyled = style.restyle_shape(_layer(session)[0], fill="#00ff00")
    assert [shape.style.fill for shape in content_children(restyled)] == ["#00ff00", "#00ff00"]
    assert [shape.style.fill for shape in mask_children(restyled)] == ["#000000"]


def test_the_style_panel_shows_the_content_style():
    group = GroupShape(50, (_rect(1, shape_style=FILLED_MASK), _rect(2)), masking=Masking("clip", (1,)))
    assert style.display_style(group).fill == "#ff0000"


def test_booleans_refuse_masked_groups():
    session = _masked_session()
    selection.set_selection(session, {50, 4})
    booleans.combine(session, "union")
    assert "Release the mask first" == session.state.status_message
    assert _ids(_layer(session)) == [50, 4]
    booleans.divide_selection(session)
    assert _ids(_layer(session)) == [50, 4]


def test_every_mask_operation_is_registered_with_a_can_run():
    for operation_id in (
        "object.clip.make",
        "object.clip.release",
        "object.mask.make",
        "object.mask.release",
        "object.mask.invert",
        "object.mask.type_luminance",
        "object.mask.type_alpha",
        "object.mask.to_mask",
        "object.mask.to_content",
    ):
        assert find(operation_id).can_run(_session()) is False
