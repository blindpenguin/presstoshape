"""SVG lengths: units, case rules, percentages per axis, the root viewport."""

import xml.etree.ElementTree as ET

import pytest

from presstoshape.formats.svg_lengths import Viewport, length, parse, resolve, root_viewport

VIEWPORT = Viewport(200.0, 100.0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10", 10),
        ("10px", 10),
        ("12pt", 16),
        ("1pc", 16),
        ("1in", 96),
        ("2.54cm", 96),
        ("25.4mm", 96),
        ("2em", 32),
        ("3ex", 24),
        ("-.5e1", -5),
        ("+7", 7),
        (" 4 ", 4),
    ],
)
def test_units_resolve_to_user_units(text, expected):
    assert length(text, "x", VIEWPORT, 16.0) == pytest.approx(expected)


def test_percentages_follow_their_axis():
    assert length("50%", "x", VIEWPORT, 16.0) == pytest.approx(100)
    assert length("50%", "y", VIEWPORT, 16.0) == pytest.approx(50)
    assert length("50%", "other", VIEWPORT, 16.0) == pytest.approx(0.5 * (200**2 + 100**2) ** 0.5 / 2**0.5)


@pytest.mark.parametrize("text", ["10PX", "1e", "--1", "", "px", "10 px", "abc", "1,5", "nan", "1em2"])
def test_invalid_attribute_lengths(text):
    assert parse(text) is None
    assert length(text, "x", VIEWPORT, 16.0) is None


def test_css_lengths_are_case_insensitive_and_canonical():
    assert parse("20PX", css=True) == (20.0, "px")
    assert parse("1EM", css=True) == (1.0, "em")
    assert parse("1E2", css=True) == (100.0, "")


def test_missing_attribute_takes_the_default():
    assert length(None, "x", VIEWPORT, 16.0, 7.0) == 7.0


def test_resolve_directly():
    assert resolve((1.0, "in"), "other", VIEWPORT, 16.0) == 96


def _root(attributes: str) -> ET.Element:
    return ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" {attributes}/>')


def test_root_viewport_prefers_the_view_box_then_size_then_100():
    assert root_viewport(_root('viewBox="0 0 300 150" width="9" height="9"')) == Viewport(300, 150)
    assert root_viewport(_root('width="2in" height="50"')) == Viewport(192, 50)
    assert root_viewport(_root("")) == Viewport(100, 100)
    assert root_viewport(_root('width="50%" height="bad"')) == Viewport(100, 100)
