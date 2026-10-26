import pytest

from presstoshape.formats.palette_files import decode_index, decode_palette, encode_index, encode_palette, file_name
from presstoshape.models.colours import Palette, Swatch


def test_palette_round_trip():
    palette = Palette(7, "PICO-8 Ünï", (Swatch(4, "Black", "#000000"), Swatch(9, "", "#1d2b53", 0.5)))
    name, swatches = decode_palette(encode_palette(palette))
    assert name == "PICO-8 Ünï"
    assert swatches == (Swatch(1, "Black", "#000000"), Swatch(2, "", "#1d2b53", 0.5))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        '{"version": 1, "swatches": []}',
        '{"version": 1, "name": " ", "swatches": []}',
        '{"version": 1, "name": "x", "swatches": [{"color": "red"}]}',
        '{"version": 9, "name": "x", "swatches": []}',
    ],
)
def test_damaged_palettes_raise(text):
    with pytest.raises(ValueError):
        decode_palette(text)


def test_index_round_trip_and_damage():
    assert decode_index(encode_index(["a.json", "b.json"])) == ["a.json", "b.json"]
    for text in ("", "{}", '{"order": [1]}'):
        with pytest.raises(ValueError):
            decode_index(text)


@pytest.mark.parametrize(
    ("name", "taken", "expected"),
    [
        ("PICO-8", [], "pico-8.json"),
        ("Grün / Blau: 2", [], "gr-n-blau-2.json"),
        ("...", [], "palette.json"),
        ("Index", [], "index-2.json"),
        ("pico-8", ["PICO-8.json"], "pico-8-2.json"),
        ("x" * 100, [], "x" * 60 + ".json"),
    ],
)
def test_file_names(name, taken, expected):
    assert file_name(name, taken) == expected
