import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import (
    booleans,
    clipboard,
    composites,
    documents,
    edit_mode,
    groups,
    images,
    masks,
    selection,
    style,
    view,
)
from presstoshape.editing.operations import shapes as shape_ops
from presstoshape.editing.registry import operations
from presstoshape.editing.session import Session
from presstoshape.models.shapes import GroupShape, ImageShape, RectShape, Style
from tests.helpers import TINY_PNG, all_shapes, quadrant_picture

WIDE = quadrant_picture(100, 50)


def raw(picture=WIDE):
    return picture.data


def new_session(width=400, height=300):
    session = Session()
    documents.new_document(session, documents.DocumentSetup(width, height, "px", 96))
    return session


def place(session, count=1, center=(200, 150), reference=False, picture=WIDE):
    return images.place_images(session, [(f"p{index}.png", raw(picture)) for index in range(count)], center, reference)


def images_in(session):
    return [shape for shape in all_shapes(session) if isinstance(shape, ImageShape)]


def command(session, name):
    entry = next(entry for entry in operations() if entry.id == name)
    return entry


def test_a_picture_is_placed_at_pixel_size_around_the_center_and_selected():
    session = new_session()
    result = place(session, center=(200, 150))
    (shape,) = images_in(session)
    assert (shape.x, shape.y, shape.width, shape.height) == (150, 125, 100, 50)
    assert shape.data == WIDE and not shape.reference and not shape.locked
    assert session.state.selection == {shape.id} and result.placed == (shape.id,) and result.refused == ()


def test_a_large_picture_shrinks_to_eighty_percent_of_the_page():
    session = new_session(400, 300)
    place(session, picture=quadrant_picture(1000, 400))
    (shape,) = images_in(session)
    assert shape.width == pytest.approx(320) and shape.height == pytest.approx(128)


def test_a_tall_picture_is_limited_by_the_page_height():
    session = new_session(400, 300)
    place(session, picture=quadrant_picture(300, 900))
    (shape,) = images_in(session)
    assert shape.height == pytest.approx(240) and shape.width == pytest.approx(80)


def test_a_picture_exactly_as_large_as_the_page_still_shrinks_by_the_margin():
    session = new_session(100, 50)
    place(session, picture=WIDE)
    (shape,) = images_in(session)
    assert shape.width == pytest.approx(80) and shape.height == pytest.approx(40)


def test_several_files_are_staggered_and_one_undo_step():
    session = new_session()
    place(session, count=3)
    first, second, third = images_in(session)
    assert (second.x - first.x, second.y - first.y) == (images.STAGGER, images.STAGGER)
    assert (third.x - second.x, third.y - second.y) == (images.STAGGER, images.STAGGER)
    assert first.data is second.data is third.data
    assert session.undo_label == "Place 3 images"
    session.undo()
    assert images_in(session) == []
    session.redo()
    assert len(images_in(session)) == 3


def test_the_undo_label_of_one_picture_is_singular():
    session = new_session()
    place(session)
    assert session.undo_label == "Place image"


def test_a_picture_goes_into_the_entered_group():
    session = new_session()
    inner = shape_ops.add_rectangle(session, (0, 0), (10, 10))
    other = shape_ops.add_rectangle(session, (20, 0), (30, 10))
    selection.set_selection(session, {inner, other})
    groups.group(session)
    (group_id,) = session.state.selection
    edit_mode.enter(session, group_id)
    place(session)
    (group,) = [shape for shape in all_shapes(session) if isinstance(shape, GroupShape)]
    assert any(isinstance(child, ImageShape) for child in group.children)


def test_pictures_are_refused_inside_a_composite():
    session = new_session()
    first = shape_ops.add_rectangle(session, (0, 0), (50, 50))
    second = shape_ops.add_rectangle(session, (20, 20), (80, 80))
    selection.set_selection(session, {first, second})
    composites.make_composite(session)
    (composite,) = session.state.selection
    edit_mode.enter(session, composite)
    result = place(session)
    assert images_in(session) == [] and result.placed == () and len(result.refused) == 1


def test_unusable_files_are_refused_and_the_rest_is_placed():
    session = new_session()
    files = [
        ("good.png", raw()),
        ("empty.png", b""),
        ("text.txt", b"hello"),
        ("broken.png", TINY_PNG[:30] + b"\0" * 40),
    ]
    result = images.place_images(session, files, (200, 150))
    assert len(result.placed) == 1
    assert [name for name, _message in result.refused] == ["empty.png", "text.txt", "broken.png"]
    assert all(name in message for name, message in result.refused)
    assert session.undo_label == "Place image"


def test_nothing_placed_is_no_undo_step_but_says_why():
    session = new_session()
    before = session.undo_label
    result = images.place_images(session, [("x.txt", b"nope")], (0, 0))
    assert result.placed == () and session.undo_label == before
    assert "x.txt" in session.state.status_message


def test_a_reference_image_goes_into_a_new_locked_bottom_layer_and_is_not_selected():
    session = new_session()
    shape_ops.add_rectangle(session, (0, 0), (10, 10))
    active = session.state.document.layers[session.state.selected_layer_index]
    place(session, reference=True)
    layers = session.state.document.layers
    assert [layer.name for layer in layers] == ["Reference", active.name]
    assert layers[0].locked
    (picture,) = layers[0].shapes
    assert picture.reference and picture.locked
    assert session.state.document.layers[session.state.selected_layer_index].name == active.name
    assert session.state.selection == set()
    assert session.undo_label == "Place reference image"
    session.undo()
    assert [layer.name for layer in session.state.document.layers] == [active.name]
    assert session.state.selected_layer_index == 0


def test_the_reference_layer_is_reused():
    session = new_session()
    place(session, reference=True)
    place(session, reference=True)
    layers = session.state.document.layers
    assert [layer.name for layer in layers].count("Reference") == 1
    assert len(layers[0].shapes) == 2


def test_reference_layer_is_named_in_the_active_language(german):
    session = new_session()
    place(session, reference=True)
    assert session.state.document.layers[0].name == "Referenz"


def selected_image(session, **fields):
    place(session)
    (shape,) = images_in(session)
    return shape


def test_commands_need_a_selected_picture():
    session = new_session()
    for name in ("image.reset_size", "image.fit_page", "image.make_reference", "image.make_artwork"):
        assert not command(session, name).can_run(session)
    selected_image(session)
    for name in ("image.reset_size", "image.fit_page", "image.make_reference"):
        assert command(session, name).can_run(session)
    assert not command(session, "image.make_artwork").can_run(session)


def test_reset_size_returns_to_pixels_about_the_center():
    session = new_session()
    picture = selected_image(session)
    from presstoshape.editing.operations import transform

    transform.set_bounds(session, picture.id, "width", 400)
    assert images_in(session)[0].width != 100
    images.reset_size(session)
    (shape,) = images_in(session)
    assert (shape.width, shape.height) == (100, 50)
    assert session.undo_label == "Reset image size"


def test_fit_page_scales_to_the_page_and_centers_it():
    session = new_session(400, 300)
    selected_image(session)
    images.fit_page(session)
    (shape,) = images_in(session)
    assert (shape.width, shape.height) == (400, 200)
    assert (shape.x, shape.y) == (0, 50)


def test_make_reference_locks_and_deselects_and_make_artwork_undoes_it():
    session = new_session()
    picture = selected_image(session)
    images.make_reference(session)
    (shape,) = images_in(session)
    assert shape.reference and shape.locked and session.state.selection == set()
    assert queries.selected_shapes(session.state) == []
    session.state.selection = {picture.id}
    assert command(session, "image.make_artwork").can_run(session)
    images.make_artwork(session)
    (shape,) = images_in(session)
    assert not shape.reference and not shape.locked and session.state.selection == {picture.id}
    session.undo()
    assert images_in(session)[0].reference


def test_replace_keeps_position_width_and_transform_and_refits_the_height():
    session = new_session()
    picture = selected_image(session)
    from dataclasses import replace

    from presstoshape.editing.operations._document import replace_shape

    with session.edit("rotate"):
        replace_shape(session.state, replace(picture, transform=(0.0, 1.0, -1.0, 0.0, 400.0, 0.0)))
    tall = quadrant_picture(50, 100)
    result = images.replace_image(session, picture.id, "tall.png", raw(tall))
    (shape,) = images_in(session)
    assert result.placed == (picture.id,)
    assert shape.data == tall and shape.width == 100 and shape.height == 200
    assert shape.x + shape.width / 2 == pytest.approx(picture.x + picture.width / 2)
    assert shape.y + shape.height / 2 == pytest.approx(picture.y + picture.height / 2)
    assert shape.transform == (0.0, 1.0, -1.0, 0.0, 400.0, 0.0)
    assert session.undo_label == "Replace image"
    session.undo()
    assert images_in(session)[0].data == WIDE


def test_replace_with_an_unusable_file_changes_nothing():
    session = new_session()
    picture = selected_image(session)
    depth = session.undo_label
    result = images.replace_image(session, picture.id, "bad.png", b"junk")
    assert result.refused and images_in(session) == [picture] and session.undo_label == depth
    assert "bad.png" in session.state.status_message


def test_replace_needs_an_image():
    session = new_session()
    rectangle = shape_ops.add_rectangle(session, (0, 0), (10, 10))
    result = images.replace_image(session, rectangle, "x.png", raw())
    assert result.placed == () and session.state.status_message == "Select an image to replace"


def test_show_and_hide_references_is_view_state_and_no_undo_step():
    session = new_session()
    place(session, reference=True)
    label = session.undo_label
    assert session.state.view.show_references
    view.set_show_references(session, False)
    assert not session.state.view.show_references and session.undo_label == label
    assert command(session, "view.show_references").checked(session) is False
    view.set_show_references(session, False)
    assert not session.state.view.show_references
    view.set_show_references(session, True)
    assert session.state.view.show_references


def two_with_image(session):
    rectangle = shape_ops.add_rectangle(session, (0, 0), (100, 100))
    place(session)
    (picture,) = images_in(session)
    selection.set_selection(session, {rectangle, picture.id})
    return rectangle, picture


@pytest.mark.parametrize(
    "run, message",
    [
        (lambda s: booleans.combine(s, "union"), "Images cannot be combined"),
        (booleans.divide_selection, "Images cannot be combined"),
        (composites.make_composite, "Images cannot be part of a Composite"),
    ],
)
def test_geometry_commands_refuse_pictures(run, message):
    session = new_session()
    two_with_image(session)
    before = list(all_shapes(session))
    run(session)
    assert all_shapes(session) == before
    assert session.state.status_message == message


def test_pictures_are_not_combinable_for_menus():
    session = new_session()
    two_with_image(session)
    assert not queries.can_combine(session.state)


def test_a_picture_cannot_be_the_clipping_path_but_can_be_masked_or_mask():
    session = new_session()
    rectangle, picture = two_with_image(session)
    assert not command(session, "object.clip.make").can_run(session)
    masks.make_clip(session)
    assert session.state.status_message == "An image cannot be a clipping path"
    assert not any(isinstance(shape, GroupShape) for shape in all_shapes(session))
    masks.make_opacity_mask(session)
    assert any(isinstance(shape, GroupShape) and shape.masking for shape in all_shapes(session))


def test_a_picture_under_a_clipping_rectangle_is_masked():
    session = new_session()
    place(session)
    (picture,) = images_in(session)
    rectangle = shape_ops.add_rectangle(session, (0, 0), (100, 100))
    selection.set_selection(session, {picture.id, rectangle})
    masks.make_clip(session)
    assert any(isinstance(shape, GroupShape) and shape.masking for shape in all_shapes(session))


def test_style_commands_change_only_the_opacity_of_a_picture():
    session = new_session()
    picture = selected_image(session)
    style.set_style(session, fill="#ff0000", stroke="#00ff00", stroke_width=9.0, opacity=0.5)
    (shape,) = images_in(session)
    assert shape.opacity == 0.5
    assert shape == ImageShape(**{**picture.__dict__, "opacity": 0.5})


def test_style_panel_shows_the_picture_opacity():
    session = new_session()
    selected_image(session)
    style.set_style(session, opacity=0.25)
    (shape,) = images_in(session)
    assert style.display_style(shape).opacity == 0.25


def test_pasting_pictures_into_a_composite_drops_them_with_a_note():
    session = new_session()
    first = shape_ops.add_rectangle(session, (0, 0), (50, 50))
    second = shape_ops.add_rectangle(session, (20, 20), (80, 80))
    selection.set_selection(session, {first, second})
    composites.make_composite(session)
    (composite,) = session.state.selection
    edit_mode.enter(session, composite)
    from presstoshape.formats.clipboard import encode_shapes

    native = encode_shapes([ImageShape(1, 0.0, 0.0, 10.0, 10.0, WIDE), RectShape(2, 0, 0, 5, 5, Style())])
    assert clipboard.paste(session, native, None, None)
    assert images_in(session) == []
    assert "images can't be Composite parts" in session.state.status_message


def test_pictures_survive_copy_and_paste():
    session = new_session()
    selected_image(session)
    content = clipboard.copy_selection(session)
    clipboard.paste(session, content.native, content.svg, (50, 50))
    first, second = images_in(session)
    assert first.data is second.data or first.data == second.data
    assert first.id != second.id


def test_the_reference_flag_is_kept_by_p2s_state():
    from presstoshape.editing.operations.documents import apply_saved_state, saved_state

    session = new_session()
    view.set_show_references(session, False)
    saved = saved_state(session.state, None)
    other = new_session()
    apply_saved_state(other.state, saved)
    assert not other.state.view.show_references
    assert saved_state(new_session().state, None).show_references is None


def test_a_reference_image_can_be_selected_in_the_tree_and_made_artwork():
    from presstoshape.editing.operations import visibility

    session = new_session()
    shape_ops.add_rectangle(session, (0, 0), (10, 10))
    place(session, reference=True)
    (picture,) = images_in(session)
    visibility.select_object(session, picture.id)
    assert session.state.selection == {picture.id}
    assert command(session, "image.make_artwork").can_run(session)
    images.make_artwork(session)
    (shape,) = images_in(session)
    assert not shape.reference and not shape.locked
    assert not session.state.document.layers[0].locked
    session.undo()
    assert images_in(session)[0].reference and session.state.document.layers[0].locked


def test_the_reference_layer_stays_locked_while_it_holds_other_references():
    from presstoshape.editing.operations import visibility

    session = new_session()
    place(session, count=2, reference=True)
    first, _second = images_in(session)
    visibility.select_object(session, first.id)
    images.make_artwork(session)
    assert session.state.document.layers[0].locked


def test_other_locked_objects_still_cannot_be_selected_in_the_tree():
    from presstoshape.editing.operations import visibility

    session = new_session()
    rectangle = shape_ops.add_rectangle(session, (0, 0), (10, 10))
    visibility.set_locked(session, rectangle, True)
    selection.set_selection(session, set())
    visibility.select_object(session, rectangle)
    assert session.state.selection == set()
