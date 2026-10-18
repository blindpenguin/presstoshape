from dataclasses import replace

import skia

from veccy.models.app_state import Document, Layer
from veccy.models.shapes import RectShape, Style
from veccy.render.paths import PathCache
from veccy.render.picture import DocumentPicture

RED = Style(fill="#ff0000", stroke=None)
GREEN = Style(fill="#00ff00", stroke=None)


def _pixels(picture: DocumentPicture, doc: Document, moving=frozenset(), offset=(0.0, 0.0)):
    surface = skia.Surface(100, 100)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    picture.draw(canvas, doc, moving, offset)
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return lambda x, y: tuple(int(v) for v in rgba[y, x])


def _doc() -> Document:
    shapes = [RectShape(1, 0, 0, 50, 50, RED), RectShape(2, 25, 25, 50, 50, GREEN), RectShape(3, 0, 60, 30, 30, RED)]
    return Document(100, 100, [Layer("L", True, shapes)])


def test_replay_matches_paint_order():
    px = _pixels(DocumentPicture(PathCache()), _doc())
    assert px(10, 10) == (255, 0, 0, 255)
    assert px(40, 40) == (0, 255, 0, 255)


def test_unchanged_document_reuses_recording():
    picture, doc = DocumentPicture(PathCache()), _doc()
    _pixels(picture, doc)
    runs = picture._runs
    _pixels(picture, doc, offset=(5, 5))
    assert picture._runs is runs


def test_document_change_rerecords():
    picture, doc = DocumentPicture(PathCache()), _doc()
    _pixels(picture, doc)
    doc.layers[0].shapes[0] = replace(doc.layers[0].shapes[0], style=GREEN)
    assert _pixels(picture, doc)(10, 10) == (0, 255, 0, 255)


def test_hidden_layer_change_rerecords():
    picture, doc = DocumentPicture(PathCache()), _doc()
    _pixels(picture, doc)
    doc.layers[0].visible = False
    assert _pixels(picture, doc)(10, 10) == (0, 0, 0, 0)


def test_moving_run_keeps_z_order_and_offset():
    picture, doc = DocumentPicture(PathCache()), _doc()
    px = _pixels(picture, doc, moving=frozenset({1}), offset=(25, 25))
    assert [moving for moving, _ in picture._runs] == [True, False]
    assert px(10, 10) == (0, 0, 0, 0)
    assert px(40, 40) == (0, 255, 0, 255)
    runs = picture._runs
    _pixels(picture, doc, moving=frozenset({1}), offset=(30, 30))
    assert picture._runs is runs
