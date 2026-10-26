import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from presstoshape.views.colour_picker import ColourPicker
from presstoshape.views.paint_pair import PaintPair
from presstoshape.views.swatch_grid import Cell, SwatchGrid, swatch_tooltip


@pytest.fixture(autouse=True)
def app():
    QApplication.instance() or QApplication([])


def picker() -> ColourPicker:
    widget = ColourPicker()
    widget.resize(220, 130)
    widget.show()
    return widget


def test_set_hsv_does_not_emit():
    widget = picker()
    spy = QSignalSpy(widget.dragged)
    widget.set_hsv((120.0, 0.5, 0.5))
    assert spy.count() == 0
    assert widget.hsv == (120.0, 0.5, 0.5)


def test_drag_in_square_sets_saturation_and_value():
    widget = picker()
    widget.set_hsv((200.0, 0.0, 0.0))
    dragged, released = QSignalSpy(widget.dragged), QSignalSpy(widget.released)
    square = widget._square()
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(round(square.left()), round(square.top())))
    QTest.mouseMove(widget, QPoint(round(square.center().x()), round(square.center().y())))
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(round(square.right()), round(square.bottom())))
    assert dragged.count() >= 1
    assert released.count() == 1
    h, s, v = widget.hsv
    assert h == 200.0
    assert s == pytest.approx(1.0, abs=0.02)
    assert v == pytest.approx(0.0, abs=0.02)


def test_drag_on_strip_sets_hue_only():
    widget = picker()
    widget.set_hsv((0.0, 0.4, 0.6))
    strip = widget._strip()
    middle = QPoint(round(strip.center().x()), round(strip.center().y()))
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=middle)
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=middle)
    h, s, v = widget.hsv
    assert h == pytest.approx(180, abs=4)
    assert (s, v) == (0.4, 0.6)


def test_paint_pair_click_activates_slot():
    pair = PaintPair()
    pair.show_paints("#ff0000", 1.0, False, None, 1.0, False, "fill")
    pair.show()
    spy = QSignalSpy(pair.activated)
    corner = pair._rect("stroke").bottomRight().toPoint() - QPoint(2, 2)
    QTest.mouseClick(pair, Qt.MouseButton.LeftButton, pos=corner)
    assert spy.count() == 1
    assert spy.at(0) == ["stroke"]


def test_swatch_grid_click_add_and_height():
    grid = SwatchGrid(add_tooltip="Add")
    grid.set_cells(tuple(Cell(index, "#000000") for index in range(10)))
    grid.resize(100, grid.heightForWidth(100))
    grid.show()
    picked, added = QSignalSpy(grid.picked), QSignalSpy(grid.add_requested)
    QTest.mouseClick(grid, Qt.MouseButton.LeftButton, pos=grid._rect(2).center().toPoint())
    QTest.mouseClick(grid, Qt.MouseButton.LeftButton, pos=grid._rect(10).center().toPoint())
    assert picked.at(0) == [2]
    assert added.count() == 1
    assert grid.heightForWidth(100) > grid.heightForWidth(400)


def test_swatch_tooltip():
    assert swatch_tooltip("", "#ff0000", 1.0) == "#ff0000"
    assert swatch_tooltip("Red", "#ff0000", 0.5) == "Red – #ff0000 (50 % opaque)"
