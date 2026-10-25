import pytest

from presstoshape.models.app_state import Tool
from presstoshape.tools.base import CursorType, Mods, resize_cursor_type
from tests.helpers import setup_tools


@pytest.mark.parametrize(
    "angle, expected",
    [
        (0, CursorType.RESIZE_H),
        (180, CursorType.RESIZE_H),
        (-170, CursorType.RESIZE_H),
        (90, CursorType.RESIZE_V),
        (-90, CursorType.RESIZE_V),
        (45, CursorType.RESIZE_FDIAG),
        (-135, CursorType.RESIZE_FDIAG),
        (135, CursorType.RESIZE_BDIAG),
        (-45, CursorType.RESIZE_BDIAG),
        (60, CursorType.RESIZE_FDIAG),
        (70, CursorType.RESIZE_V),
    ],
)
def test_resize_cursor_type_picks_nearest(angle, expected):
    assert resize_cursor_type(angle) is expected


def test_switch_calls_leave_after_the_active_tool_changed():
    session, g = setup_tools()
    g.set_tool(Tool.PEN)
    pen = g.toolbox.active
    seen = []

    def leave():
        seen.append(g.toolbox.active)
        # A commit notifies, and the canvas refresh switches to the same tool again: nothing happens.
        g.set_tool(Tool.SELECT)

    pen.leave = leave
    g.set_tool(Tool.SELECT)
    assert seen == [g.toolbox.active] and g.toolbox.active is not pen


def test_other_tools_cancel_their_gesture_on_switch():
    session, g = setup_tools()
    g.set_tool(Tool.RECTANGLE)
    g.press((0, 0), Mods())
    g.move((40, 40), Mods())
    rectangle = g.toolbox.active
    g.set_tool(Tool.SELECT)
    assert not rectangle.active and session.state.document.layers[0].shapes == []
