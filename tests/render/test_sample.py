from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import RectShape, Style
from presstoshape.render.paths import PathCache
from presstoshape.render.sample import color_at

DOCUMENT = Document(
    width=100,
    height=100,
    layers=[
        Layer(
            "L",
            True,
            [
                RectShape(1, 10, 10, 20, 20, Style(fill="#ff0000", stroke=None)),
                RectShape(2, 50, 10, 20, 20, Style(fill="#0000ff", stroke=None, fill_opacity=0.5)),
                RectShape(3, 150, 10, 20, 20, Style(fill="#00ff00", stroke=None)),
            ],
        )
    ],
)


def sample(point, zoom=1.0):
    return color_at(DOCUMENT, PathCache(), point, zoom, True, "#ffffff")


def test_solid_shape():
    assert sample((15, 15)) == "#ff0000"
    assert sample((15, 15), zoom=4.0) == "#ff0000"


def test_half_transparent_shape_over_the_page():
    assert sample((60, 15)) in ("#7f7fff", "#8080ff")


def test_page_and_pasteboard():
    assert sample((90, 90)) == "#ffffff"
    assert sample((150, 150)) is None
    assert sample((155, 15)) == "#00ff00"
