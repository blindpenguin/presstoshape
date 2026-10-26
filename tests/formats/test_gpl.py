import pytest

from presstoshape.formats.gpl import read_gpl, write_gpl

GIMP = """GIMP Palette
Name: Bears
Columns: 16
#
  8   8   8\tgrey3
 68  44  44\tUntitled
255 255 255
"""

INKSCAPE = "GIMP Palette\r\nName: Inkscape default\r\n# comment\r\n  0   0   0  Black (#000000)\r\n255 0 0 Red\r\n"

KRITA = """GIMP Palette
Name: Krita
Columns: 8
#
200 30 30\tRed\t
 12 12 400\tToo blue
abc 1 2 broken
1 2\tshort
"""


def test_reads_gimp_palette():
    assert read_gpl(GIMP) == [("grey3", "#080808"), ("Untitled", "#442c2c"), ("", "#ffffff")]


def test_reads_inkscape_palette_with_crlf():
    assert read_gpl(INKSCAPE) == [("Black (#000000)", "#000000"), ("Red", "#ff0000")]


def test_skips_lines_that_are_not_colours():
    assert read_gpl(KRITA) == [("Red", "#c81e1e")]


@pytest.mark.parametrize("text", ["", "Name: x\n1 2 3", "JASC-PAL\n0100\n"])
def test_refuses_other_files(text):
    with pytest.raises(ValueError):
        read_gpl(text)


def test_write_and_read_back():
    text = write_gpl("My  palette", [("Rose", "#e11d48"), ("", "#000000"), ("two\twords", "#0ea5e9")])
    assert text.startswith("GIMP Palette\nName: My palette\n")
    assert read_gpl(text) == [("Rose", "#e11d48"), ("", "#000000"), ("two words", "#0ea5e9")]
