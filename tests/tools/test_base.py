import pytest

from presstoshape.tools.base import CursorType, resize_cursor_type


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
