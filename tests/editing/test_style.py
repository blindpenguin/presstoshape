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
