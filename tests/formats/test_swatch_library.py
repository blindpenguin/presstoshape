import pytest

from presstoshape.formats.swatch_library import read_library, write_library
from presstoshape.models.colours import Swatch


def test_round_trip_numbers_swatches_from_one():
    swatches = (Swatch(7, "Rose", "#e11d48"), Swatch(9, "Ünïcode", "#0ea5e9", 0.25))
    assert read_library(write_library(swatches)) == (
        Swatch(1, "Rose", "#e11d48"),
        Swatch(2, "Ünïcode", "#0ea5e9", 0.25),
    )


def test_empty_library():
    assert read_library(write_library(())) == ()


def test_opacity_is_clamped_and_colour_lowered():
    text = '{"version": 1, "swatches": [{"color": "#ABCDEF", "opacity": 3}]}'
    assert read_library(text) == (Swatch(1, "", "#abcdef", 1.0),)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        "{}",
        '{"version": 2, "swatches": []}',
        '{"version": 1}',
        '{"version": 1, "swatches": [1]}',
        '{"version": 1, "swatches": [{"color": "red"}]}',
        '{"version": 1, "swatches": [{"color": "#000000", "name": 4}]}',
        '{"version": 1, "swatches": [{"color": "#000000", "opacity": "x"}]}',
        '{"version": 1, "swatches": [{"color": "#000000", "opacity": NaN}]}',
    ],
)
def test_malformed_libraries_raise(text):
    with pytest.raises(ValueError):
        read_library(text)
