import itertools

import pytest

from presstoshape.geometry.colours import (
    hex_to_rgb,
    hsv_for,
    hsv_to_hex,
    hsv_to_rgb,
    parse_hex_input,
    rgb_to_hex,
    rgb_to_hsv,
)


def test_hex_and_rgb():
    assert hex_to_rgb("#3b82f6") == (59, 130, 246)
    assert hex_to_rgb("#fff") == (255, 255, 255)
    assert rgb_to_hex((59, 130, 246)) == "#3b82f6"
    assert rgb_to_hex((300, -4, 0)) == "#ff0000"


@pytest.mark.parametrize("grey", range(256))
def test_greys_survive_hsv(grey):
    color = rgb_to_hex((grey, grey, grey))
    assert hsv_to_hex(rgb_to_hsv(hex_to_rgb(color))) == color


def test_colours_survive_hsv():
    for rgb in itertools.product(range(0, 256, 15), repeat=3):
        assert hsv_to_rgb(rgb_to_hsv(rgb)) == rgb


def test_hsv_ranges():
    assert rgb_to_hsv((255, 0, 0)) == (0.0, 1.0, 1.0)
    h, s, v = rgb_to_hsv((0, 0, 255))
    assert h == pytest.approx(240)
    assert hsv_to_rgb((360, 1, 1)) == (255, 0, 0)


def test_hsv_for_keeps_hue_of_grey_and_black():
    previous = (210.0, 0.7, 0.9)
    assert hsv_for("#000000", previous) == (210.0, 0.7, 0.0)
    h, s, v = hsv_for("#808080", previous)
    assert (h, s) == (210.0, 0.0)
    assert v == pytest.approx(128 / 255)
    h, s, v = hsv_for("#ff0000", previous)
    assert (h, s, v) == (0.0, 1.0, 1.0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#3B82F6", "#3b82f6"),
        ("3b82f6", "#3b82f6"),
        ("#abc", "#aabbcc"),
        (" abc ", "#aabbcc"),
        ("", None),
        ("#12345", None),
        ("zzzzzz", None),
    ],
)
def test_parse_hex_input(text, expected):
    assert parse_hex_input(text) == expected


def test_parse_hex_input_keywords():
    names = {"teal": "#008080"}
    assert parse_hex_input("teal", names.get) == "#008080"
    assert parse_hex_input("nope", names.get) is None
