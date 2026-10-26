from dataclasses import replace

from presstoshape.editing import queries
from presstoshape.editing.operations import colours, groups, images, selection, shapes, style, view
from presstoshape.editing.registry import find
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.colours import RECENT_LIMIT
from presstoshape.models.shapes import (
    GradientStop,
    GroupShape,
    LinearGradient,
    Masking,
    RectShape,
    Style,
)
from tests.helpers import TINY_PNG, all_shapes

GRADIENT = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff")))


def two_rects(session: Session) -> None:
    shapes.add_rectangle(session, (0, 0), (10, 10))
    shapes.add_rectangle(session, (20, 0), (30, 10))
    selection.set_selection(session, {shape.id for shape in all_shapes(session)})


def test_target_follows_selection_tool_and_current(session):
    assert queries.colour_target(session.state) == "current"
    view.select_tool(session, Tool.RECTANGLE)
    assert queries.colour_target(session.state) == "tool"
    two_rects(session)
    assert queries.colour_target(session.state) == "selection"


def test_images_only_selection_is_disabled(session):
    images.place_images(session, [("a.png", TINY_PNG)], (50, 50))
    assert queries.colour_target(session.state) == "disabled"
    assert not find("colour.swap").can_run(session)
    colours.apply_colour(session, "#00ff00")
    assert all(s.style.fill != "#00ff00" for s in all_shapes(session) if hasattr(s, "style"))


def test_apply_colour_to_selection_is_one_undo_step(session):
    two_rects(session)
    colours.apply_colour(session, "#00ff00", 0.5)
    assert {s.style.fill for s in all_shapes(session)} == {"#00ff00"}
    assert {s.style.fill_opacity for s in all_shapes(session)} == {0.5}
    assert session.undo_label == "Change fill"
    assert session.state.colours.recent[0] == "#00ff00"


def test_apply_to_stroke_when_stroke_is_active(session):
    two_rects(session)
    colours.toggle_active_paint(session)
    assert session.state.colours.active == "stroke"
    colours.apply_colour(session, "#123456")
    assert {s.style.stroke for s in all_shapes(session)} == {"#123456"}
    assert session.undo_label == "Change stroke"


def test_merged_steps_make_one_undo_step_and_are_not_remembered(session):
    two_rects(session)
    count = session.undo_count
    for color in ("#000001", "#000002", "#000003"):
        colours.apply_colour(session, color, merge_key="colour.fill")
    assert session.undo_count == count + 1
    assert session.state.colours.recent == ()
    session.end_merge()
    colours.apply_colour(session, "#000004", merge_key="colour.fill")
    assert session.undo_count == count + 2


def test_gradient_is_replaced_by_colour(session):
    two_rects(session)
    style.set_fill(session, GRADIENT)
    colours.apply_colour(session, "#abcdef")
    assert all_shapes(session)[0].style.fill == "#abcdef"


def test_tool_target_changes_tool_style_without_undo(session):
    view.select_tool(session, Tool.ELLIPSE)
    colours.apply_colour(session, "#00ff00", 0.25)
    assert session.state.tool_styles[Tool.ELLIPSE].fill == "#00ff00"
    assert session.state.tool_styles[Tool.ELLIPSE].fill_opacity == 0.25
    assert not session.can_undo


def test_current_target(session):
    colours.apply_colour(session, "#00ff00")
    assert session.state.colours.current.fill == "#00ff00"
    assert colours.target_style(session.state) is session.state.colours.current


def test_target_paint_reports_mixed(session):
    two_rects(session)
    first = all_shapes(session)[0]
    selection.set_selection(session, {first.id})
    colours.apply_colour(session, "#111111")
    selection.set_selection(session, {s.id for s in all_shapes(session)})
    assert colours.target_paint(session.state, "fill") is colours.MIXED
    assert colours.target_paint(session.state, "stroke") == all_shapes(session)[0].style.stroke


def test_none_swap_default(session):
    two_rects(session)
    colours.apply_colour(session, "#00ff00", 0.5)
    colours.set_paint_none(session)
    assert all_shapes(session)[0].style.fill is None
    session.undo()
    stroke = all_shapes(session)[0].style.stroke
    colours.swap_paints(session)
    swapped = all_shapes(session)[0].style
    assert (swapped.fill, swapped.stroke, swapped.stroke_opacity) == (stroke, "#00ff00", 0.5)
    assert session.undo_label == "Swap fill and stroke"
    colours.default_paints(session)
    default = Style()
    restored = all_shapes(session)[0].style
    assert (restored.fill, restored.stroke, restored.fill_opacity) == (default.fill, default.stroke, 1.0)


def test_swap_reaches_group_children_but_not_masks(session):
    content = RectShape(1, 0, 0, 10, 10, Style(fill="#ff0000", stroke="#00ff00"))
    mask = RectShape(2, 0, 0, 10, 10, Style(fill="#ffffff", stroke=None))
    group = GroupShape(3, (mask, content), masking=Masking("luminance", (2,)))
    session.state.document = Document(layers=[Layer("L", shapes=[group])], next_id=4)
    selection.set_selection(session, {3})
    colours.swap_paints(session)
    result = all_shapes(session)[0]
    assert result.children[0] == mask
    assert (result.children[1].style.fill, result.children[1].style.stroke) == ("#00ff00", "#ff0000")


def test_pick_up_style_on_selection_keeps_geometry(session):
    two_rects(session)
    first, second = all_shapes(session)
    selection.set_selection(session, {second.id})
    source = Style(fill=GRADIENT, stroke="#00ff00", stroke_width=7, dashes=(2.0, 1.0), opacity=0.5)
    colours.pick_up_style(session, source)
    picked = all_shapes(session)[1]
    assert picked.style == source
    assert (picked.x, picked.width) == (second.x, second.width)
    assert session.state.selection == {second.id}
    assert session.undo_label == "Pick up style"
    assert session.state.colours.recent[:2] == ("#ff0000", "#00ff00")


def test_pick_up_style_without_selection_fills_current_colour(session):
    shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, set())
    count = session.undo_count
    colours.pick_up_style(session, Style(fill="#010203", stroke=None, stroke_width=9, fill_opacity=0.5))
    current = session.state.colours.current
    assert (current.fill, current.stroke, current.fill_opacity, current.stroke_width) == (
        "#010203",
        None,
        0.5,
        Style().stroke_width,
    )
    assert session.undo_count == count


def test_recent_colours_order_dedupe_and_limit(session):
    for index in range(RECENT_LIMIT + 4):
        colours.remember_colour(session, f"#0000{index:02x}")
    colours.remember_colour(session, "#000003")
    recent = session.state.colours.recent
    assert len(recent) == RECENT_LIMIT
    assert recent[0] == "#000003"
    assert recent.count("#000003") == 1
    colours.clear_recent_colours(session)
    assert session.state.colours.recent == ()


def test_document_colours_in_paint_order_without_masks_hidden_or_parts(session):
    content = RectShape(1, 0, 0, 1, 1, Style(fill="#ff0000", stroke="#00FF00"))
    mask = RectShape(2, 0, 0, 1, 1, Style(fill="#ffffff", stroke=None))
    group = GroupShape(3, (mask, content), masking=Masking("clip", (2,)))
    gradient = RectShape(4, 0, 0, 1, 1, Style(fill=GRADIENT, stroke="#ff0000"))
    hidden = replace(RectShape(5, 0, 0, 1, 1, Style(fill="#999999")), hidden=True)
    document = Document(
        layers=[Layer("A", shapes=[group, gradient, hidden]), Layer("B", visible=False, shapes=[hidden])]
    )
    assert queries.document_colours(document) == ["#ff0000", "#00ff00", "#0000ff"]


def test_group_selection_shows_first_leaf(session):
    two_rects(session)
    colours.apply_colour(session, "#222222")
    groups.group(session)
    assert colours.target_style(session.state).fill == "#222222"
