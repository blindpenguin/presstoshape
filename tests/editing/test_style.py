import pytest

from presstoshape.editing.operations import shapes, style
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
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
