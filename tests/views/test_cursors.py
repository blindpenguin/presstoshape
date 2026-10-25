from PySide6.QtWidgets import QApplication

from presstoshape.tools.base import CursorType
from presstoshape.views.cursors import _CUSTOM, qt_cursor


def test_custom_cursors_point_with_the_arrow_tip():
    QApplication.instance() or QApplication([])
    for cursor_type in _CUSTOM:
        cursor = qt_cursor(cursor_type, 1.0)
        assert (cursor.hotSpot().x(), cursor.hotSpot().y()) == (2, 2)
        image = cursor.pixmap().toImage()
        # The arrow's dark ink is right at the hotspot, the badge sits away from it.
        assert image.pixelColor(3, 8).lightness() < 80
        assert any(image.pixelColor(x, y).alpha() > 0 for x in range(16, 31) for y in range(16, 31))
    assert qt_cursor(CursorType.CROSS, 1.0).pixmap().isNull()
