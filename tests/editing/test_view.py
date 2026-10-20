from presstoshape.editing.operations import shapes, view
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import PathShape, TextShape
from tests.helpers import all_shapes


def test_notifies_listeners_on_change():
    session = Session()
    calls = []
    session.subscribe(lambda: calls.append(1))
    view.select_tool(session, Tool.PEN)
    assert calls == [1]


def test_tool_style_applies_to_that_tool_only_and_is_not_undoable():
    session = Session()
    view.set_tool_style(session, Tool.ELLIPSE, fill="#00ff00", stroke_width=-3)
    assert not session.can_undo and not session.state.dirty
    assert session.state.tool_styles[Tool.ELLIPSE].stroke_width == 0
    shapes.add_rectangle(session, (0, 0), (10, 10))
    shapes.add_ellipse(session, (0, 0), (10, 10))
    rect, ellipse = all_shapes(session)
    assert rect.style.fill != "#00ff00"
    assert ellipse.style.fill == "#00ff00"


def test_default_pen_has_no_fill_and_text_has_no_stroke():
    session = Session()
    view.set_font_size(session, 40)
    shapes.add_path(session, [(0, 0), (10, 10), (20, 0)])
    shapes.add_text(session, (5, 5), "hi")
    path, text = all_shapes(session)
    assert isinstance(path, PathShape) and path.style.fill is None
    assert isinstance(text, TextShape) and text.style.stroke is None
    assert text.font_size == 40


def test_zoom_clamped():
    session = Session()
    view.set_zoom(session, 5000)
    assert session.state.zoom_percent == 800
    view.set_zoom(session, 1)
    assert session.state.zoom_percent == 10


def test_tool_styles_are_brought_into_range():
    session = Session()
    view.set_tool_style(session, Tool.RECTANGLE, opacity=-1, dashes=(1, 2, 3), stroke_width=-2)
    tool_style = session.state.tool_styles[Tool.RECTANGLE]
    assert (tool_style.opacity, tool_style.dashes, tool_style.stroke_width) == (0, (1, 2, 3, 1, 2, 3), 0)
