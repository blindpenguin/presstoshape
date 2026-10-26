import pytest

from presstoshape.formats.palettes import (
    MAX_IMAGE_COLORS,
    WRITE_SUFFIXES,
    colors_from_pixels,
    read_palette,
    write_palette,
)

# As Lospec writes them (CRLF line ends, its comments and header lines).
LOSPEC_HEX = "000000\r\n1D2B53\r\nFFCCAA\r\n"
LOSPEC_PAL = "JASC-PAL\r\n0100\r\n3\r\n0 0 0\r\n29 43 83\r\n255 204 170\r\n"
LOSPEC_TXT = (
    ";paint.net Palette File\r\n;Downloaded from Lospec.com/palette-list\r\n;Palette Name: Test\r\n"
    ";Description: A <a href='x'>test</a>.\r\n;Colors: 3\r\nFF000000\r\nFF1D2B53\r\n80FFCCAA\r\n"
)
LOSPEC_GPL = "GIMP Palette\r\n#Palette Name: Test\r\n#Colors: 3\r\n0\t0\t0\t000000\r\n29\t43\t83\t1D2B53\r\n255\t204\t170\tffccaa\r\n"
EXPECTED = [("", "#000000", 1.0), ("", "#1d2b53", 1.0), ("", "#ffccaa", 1.0)]


@pytest.mark.parametrize(("suffix", "text"), [(".hex", LOSPEC_HEX), (".pal", LOSPEC_PAL), (".gpl", LOSPEC_GPL)])
def test_lospec_downloads(suffix, text):
    assert read_palette(suffix, text) == EXPECTED


def test_paint_net_alpha_becomes_opacity():
    assert read_palette(".txt", LOSPEC_TXT) == [*EXPECTED[:2], ("", "#ffccaa", 0.502)]


def test_header_wins_over_suffix():
    assert read_palette(".txt", LOSPEC_PAL) == EXPECTED
    assert read_palette(".pal", LOSPEC_GPL) == EXPECTED


def test_gimp_names_are_kept_unless_they_repeat_the_colour():
    text = "GIMP Palette\n255 0 0\tRed\n0 255 0\t#00FF00\n"
    assert read_palette(".gpl", text) == [("Red", "#ff0000", 1.0), ("", "#00ff00", 1.0)]


def test_hex_accepts_hash_and_blank_lines():
    assert read_palette(".hex", "#000000\n\n1d2b53\n") == EXPECTED[:2]


@pytest.mark.parametrize(
    ("suffix", "text"),
    [
        (".hex", ""),
        (".hex", "000000\nnot a colour\n"),
        (".txt", ";paint.net Palette File\nFF00\n"),
        (".txt", ""),
        (".pal", "JASC\n"),
        (".gpl", "Name: x\n"),
        (".aco", "anything"),
    ],
)
def test_other_text_is_refused(suffix, text):
    with pytest.raises(ValueError):
        read_palette(suffix, text)


def test_image_colours_in_reading_order_without_repeats_or_transparency():
    red, blue, clear = bytes((255, 0, 0, 255)), bytes((0, 0, 255, 128)), bytes((9, 9, 9, 0))
    pixels = red + red + blue + clear + red + blue
    assert colors_from_pixels(3, 2, pixels) == [("", "#ff0000", 1.0), ("", "#0000ff", 0.502)]


def test_photos_are_not_palettes():
    count = MAX_IMAGE_COLORS + 1
    pixels = b"".join(bytes((i % 256, i // 256, 0, 255)) for i in range(count))
    with pytest.raises(ValueError):
        colors_from_pixels(count, 1, pixels)
    with pytest.raises(ValueError):
        colors_from_pixels(2, 2, bytes(4))


@pytest.mark.parametrize("suffix", WRITE_SUFFIXES)
def test_written_palettes_read_back(suffix):
    colors = [("Rose", "#e11d48", 1.0), ("", "#0ea5e9", 0.5)]
    reread = read_palette(suffix, write_palette(suffix, "My palette", colors))
    assert [color for _name, color, _opacity in reread] == ["#e11d48", "#0ea5e9"]
    if suffix == ".txt":
        assert [opacity for _name, _color, opacity in reread] == [1.0, 0.502]
    if suffix == ".gpl":
        assert reread[0][0] == "Rose"
