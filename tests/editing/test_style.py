import pytest

from presstoshape.editing.operations import shapes, style
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import GradientStop, GroupShape, LinearGradient, RadialGradient
from tests.helpers import all_shapes


def test_stroke_width_changes_merge_into_one_undo_step():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    for w in (3, 4, 5):
        style.set_stroke_width(session, w)
    assert all_shapes(session)[0].style.stroke_width == 5
    session.undo()
    assert all_shapes(session)[0].style.stroke_width == 2


def test_selection_style_without_selection_is_noop():
    session = Session()
    before = dict(session.state.tool_styles)
    style.set_fill(session, "#00ff00")
    assert session.state.tool_styles == before
    assert not session.can_undo


def test_selection_style_leaves_tool_styles_alone():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    style.set_fill(session, "#00ff00")
    assert all_shapes(session)[0].style.fill == "#00ff00"
    assert session.state.tool_styles[Tool.RECTANGLE].fill != "#00ff00"


@pytest.mark.parametrize(
    "changes, label",
    [
        ({"opacity": 0.5}, "Change opacity"),
        ({"fill_opacity": 0.5}, "Change fill opacity"),
        ({"stroke_opacity": 0.5}, "Change stroke opacity"),
        ({"fill_rule": "evenodd"}, "Change fill rule"),
        ({"cap": "round"}, "Change line cap"),
        ({"join": "bevel"}, "Change line join"),
        ({"miter_limit": 8}, "Change mitre limit"),
        ({"dashes": (4, 2)}, "Change dashes"),
        ({"dash_offset": 1}, "Change dash offset"),
        ({"cap": "round", "join": "round"}, "Change style"),
    ],
)
def test_each_style_field_is_one_named_undo_step(changes, label):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    before = all_shapes(session)[0].style
    style.set_style(session, **changes)
    assert session.undo_label == label
    assert all(getattr(all_shapes(session)[0].style, key) == value for key, value in changes.items())
    session.undo()
    assert all_shapes(session)[0].style == before


def test_slider_steps_merge_but_switches_do_not():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    for value in (0.9, 0.8, 0.7):
        style.set_style(session, opacity=value)
    style.set_style(session, cap="round")
    style.set_style(session, cap="square")
    session.undo()
    session.undo()
    assert all_shapes(session)[0].style.opacity == 0.7
    session.undo()
    assert all_shapes(session)[0].style.opacity == 1.0


def test_values_are_brought_into_range():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    style.set_style(session, opacity=3, dashes=(5,), fill_rule="odd", stroke_width=-1)
    result = all_shapes(session)[0].style
    assert (result.opacity, result.dashes, result.fill_rule, result.stroke_width) == (1, (5, 5), "nonzero", 0)


def test_unknown_fields_are_refused():
    with pytest.raises(ValueError):
        style.set_style(Session(), sparkle=True)


GRADIENT = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff", 0.5)))


def _gradient_rectangle() -> Session:
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    style.set_fill(session, GRADIENT)
    style.set_stroke(session, GRADIENT)
    return session


def test_gradients_can_be_set_and_undone():
    session = _gradient_rectangle()
    assert all_shapes(session)[0].style.fill == GRADIENT
    session.undo()
    assert all_shapes(session)[0].style.stroke != GRADIENT


@pytest.mark.parametrize(
    "changes",
    [
        {"stroke_width": 9.0},
        {"opacity": 0.4},
        {"fill_opacity": 0.2, "stroke_opacity": 0.3},
        {"cap": "round", "join": "bevel", "miter_limit": 2.0},
        {"dashes": (4, 2), "dash_offset": 1.0},
        {"fill_rule": "evenodd"},
    ],
)
def test_unrelated_style_changes_keep_gradients(changes):
    session = _gradient_rectangle()
    style.set_style(session, **changes)
    shape = all_shapes(session)[0]
    assert shape.style.fill == GRADIENT and shape.style.stroke == GRADIENT


def test_a_flat_colour_replaces_a_gradient_and_undo_brings_it_back():
    session = _gradient_rectangle()
    style.set_fill(session, "#00ff00")
    style.set_stroke(session, None)
    shape = all_shapes(session)[0]
    assert (shape.style.fill, shape.style.stroke) == ("#00ff00", None)
    session.undo()
    session.undo()
    assert all_shapes(session)[0].style.fill == GRADIENT


def test_gradient_is_handed_to_every_shape_in_a_group_and_shown_for_it():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    shapes.add_rectangle(session, (20, 0), (30, 10))
    from presstoshape.editing.operations import groups, selection

    selection.select_all(session)
    groups.group(session)
    radial = RadialGradient(0.5, 0.5, 0.5, 0.5, 0.5, GRADIENT.stops)
    style.set_fill(session, radial)
    (group,) = session.state.document.layers[0].shapes
    assert isinstance(group, GroupShape)
    assert all(child.style.fill == radial for child in group.children)
    assert style.display_style(group).fill == radial
