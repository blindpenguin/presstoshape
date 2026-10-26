from presstoshape.formats.svg import read_svg, read_svg_with_notes, write_shapes_svg, write_svg
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.colours import Swatch
from presstoshape.models.shapes import RectShape, Style

INKSCAPE_1 = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="100" height="100">
  <defs>
    <linearGradient id="swatch1" inkscape:swatch="solid" inkscape:label="Brand">
      <stop style="stop-color:#E11D48;stop-opacity:1;" offset="0"/>
    </linearGradient>
    <linearGradient id="swatch2" inkscape:swatch="solid">
      <stop style="stop-color:#0ea5e9;stop-opacity:0.5;" offset="0"/>
    </linearGradient>
    <linearGradient id="grad" inkscape:swatch="gradient">
      <stop style="stop-color:#000" offset="0"/><stop style="stop-color:#fff" offset="1"/>
    </linearGradient>
    <linearGradient id="use" xlink:href="#swatch1" x1="0" x2="1"/>
  </defs>
  <rect width="10" height="10" fill="url(#swatch1)"/>
  <rect x="20" width="10" height="10" fill="url(#use)"/>
</svg>"""

INKSCAPE_092 = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:osb="http://www.openswatchbook.org/uri/2009/osb"
  width="10" height="10">
  <defs>
    <linearGradient id="Old" osb:paint="solid"><stop offset="0" stop-color="teal"/></linearGradient>
  </defs>
</svg>"""


def test_inkscape_swatches_are_read():
    document, notes = read_svg_with_notes(INKSCAPE_1)
    assert [(s.name, s.color, s.opacity) for s in document.swatches] == [
        ("Brand", "#e11d48", 1.0),
        ("swatch2", "#0ea5e9", 0.5),
    ]
    assert any("gradient swatch" in note for note in notes)
    shape_ids = {shape.id for layer in document.layers for shape in layer.shapes}
    assert not shape_ids & {s.id for s in document.swatches}
    assert document.next_id > max(s.id for s in document.swatches)


def test_shapes_using_a_swatch_get_its_colour():
    document = read_svg(INKSCAPE_1)
    fills = [shape.style.fill for shape in document.layers[0].shapes]
    assert fills == ["#e11d48", "#e11d48"]


def test_inkscape_092_swatches_are_read():
    (swatch,) = read_svg(INKSCAPE_092).swatches
    assert (swatch.name, swatch.color) == ("Old", "#008080")


def test_swatches_round_trip_through_svg():
    swatches = (Swatch(2, "Rose & co", "#e11d48"), Swatch(3, "", "#0ea5e9", 0.25))
    document = Document(layers=[Layer("L", True, [RectShape(1, 0, 0, 5, 5, Style())])], next_id=4, swatches=swatches)
    text = write_svg(document)
    assert 'inkscape:swatch="solid"' in text
    reread = read_svg(text).swatches
    assert [(s.name, s.color, s.opacity) for s in reread] == [
        ("Rose & co", "#e11d48", 1.0),
        ("swatch2", "#0ea5e9", 0.25),
    ]


def test_clipboard_svg_has_no_swatches():
    text = write_shapes_svg([RectShape(1, 0, 0, 5, 5, Style())], (0, 0, 5, 5))
    assert "swatch" not in text
