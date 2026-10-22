"""Property value validation: what the cascade accepts, and canonical forms."""

import pytest

from presstoshape.formats.svg_properties import is_color, normalize


@pytest.mark.parametrize(
    "value",
    ["red", "RED", "#abc", "#abcd", "#aabbcc", "#aabbccdd", "rgb(1,2,3)", "rgba(1, 2, 3, .5)", "hsl(120 50% 50%)"],
)
def test_valid_colours(value):
    assert is_color(value)
    assert normalize("fill", value, css=True) == value


@pytest.mark.parametrize(
    "value", ["", "garbage", "#12345", "#gggggg", "rgb(1,2)", "ActiveBorder", "Window", "red blue", "rgb(1,2,3", "12"]
)
def test_invalid_colours(value):
    assert normalize("fill", value, css=True) is None
    assert normalize("stroke", value, css=False) is None
    assert normalize("color", value, css=True) is None


def test_black_and_transparent_are_colours():
    assert is_color("black") and is_color("BLACK") and is_color("transparent")


def test_paint_keywords_and_references():
    assert normalize("fill", "none", css=False) == "none"
    assert normalize("fill", "NONE", css=True) == "none"
    assert normalize("fill", "NONE", css=False) is None
    assert normalize("fill", "currentColor", css=False) == "currentColor"
    assert normalize("fill", "CURRENTCOLOR", css=True) == "currentColor"
    assert normalize("fill", "currentcolor", css=False) is None
    assert normalize("fill", "url(#g)", css=False) == "url(#g)"
    assert normalize("fill", "url(#g) red", css=False) == "url(#g) red"
    assert normalize("fill", "url(#g) none", css=False) == "url(#g) none"
    assert normalize("fill", "url(#g) nonsense", css=False) is None
    assert normalize("fill", "url(#g", css=False) is None


def test_color_accepts_current_color_and_colours():
    assert normalize("color", "currentColor", css=False) == "currentColor"
    assert normalize("color", "#fff", css=False) == "#fff"


def test_inherit_is_valid_everywhere():
    for name in ("fill", "color", "stroke-width", "opacity", "display", "stroke-linecap"):
        assert normalize(name, "inherit", css=False) == "inherit"


def test_lengths_follow_the_case_rules():
    assert normalize("stroke-width", "10PX", css=False) is None
    assert normalize("stroke-width", "20PX", css=True) == "20.0px"
    assert normalize("stroke-width", "-1", css=True) is None
    assert normalize("stroke-dashoffset", "-3", css=False) == "-3.0"
    assert normalize("font-size", "12pt", css=False) == "12.0pt"
    assert normalize("font-size", "larger", css=True) == "larger"
    assert normalize("font-size", "huge", css=True) is None
    assert normalize("font-size", "-2", css=False) is None


def test_dasharray():
    assert normalize("stroke-dasharray", "none", css=False) == "none"
    assert normalize("stroke-dasharray", "5, 3 2", css=False) == "5.0 3.0 2.0"
    assert normalize("stroke-dasharray", "5, -3", css=False) is None
    assert normalize("stroke-dasharray", "5 x", css=False) is None
    assert normalize("stroke-dasharray", "", css=False) is None


def test_opacity_and_miterlimit():
    assert normalize("opacity", "0.5", css=False) == "0.5"
    assert normalize("fill-opacity", "50%", css=False) == "50%"
    assert normalize("opacity", "half", css=False) is None
    assert normalize("stroke-miterlimit", "4", css=False) == "4"
    assert normalize("stroke-miterlimit", "0.5", css=False) is None


def test_enums():
    assert normalize("stroke-linecap", "round", css=False) == "round"
    assert normalize("stroke-linecap", "ROUND", css=False) is None
    assert normalize("stroke-linecap", "ROUND", css=True) == "round"
    assert normalize("visibility", "hidden", css=False) == "hidden"
    assert normalize("display", "flex-ish", css=False) is None
    assert normalize("fill-rule", "evenodd", css=False) == "evenodd"


def test_unknown_properties_pass_through():
    assert normalize("clip-path", " url(#c) ", css=False) == "url(#c)"
