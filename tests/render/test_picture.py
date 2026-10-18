from dataclasses import replace

import skia

from presstoshape.geometry import affine
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import RectShape, Style
from presstoshape.render.paths import PathCache
from presstoshape.render.picture import DocumentPicture

RED = Style(fill="#ff0000", stroke=None)
GREEN = Style(fill="#00ff00", stroke=None)


def _pixels(picture: DocumentPicture, doc: Document, moving=frozenset(), offset=(0.0, 0.0), live=(), matrix=None):
    surface = skia.Surface(100, 100)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    picture.draw(canvas, doc, moving, matrix or affine.translation(*offset), live)
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
    assert [moving for moving, _, _ in picture._runs] == [True, False]
    assert px(10, 10) == (0, 0, 0, 0)
    assert px(40, 40) == (0, 255, 0, 255)
    runs = picture._runs
    _pixels(picture, doc, moving=frozenset({1}), offset=(30, 30))
    assert picture._runs is runs


def test_live_shapes_replace_moving_run_without_rerecording():
    picture, doc = DocumentPicture(PathCache()), _doc()
    _pixels(picture, doc, moving=frozenset({1}))
    runs = picture._runs
    live = (replace(doc.layers[0].shapes[0], x=60, y=0),)
    px = _pixels(picture, doc, moving=frozenset({1}), live=live)
    assert picture._runs is runs
    assert px(10, 10) == (0, 0, 0, 0)
    assert px(70, 10) == (255, 0, 0, 255)


def test_moving_run_under_rotation_matrix():
    picture, doc = DocumentPicture(PathCache()), _doc()
    # Shape 3 (0,60 30x30) rotated 90° about (45, 75) lands at x 30..60, y 60..90 mirrored around the center.
    px = _pixels(picture, doc, moving=frozenset({3}), matrix=affine.rotation(3.141592653589793 / 2, 45, 75))
    assert px(5, 75) == (0, 0, 0, 0)
    assert px(50, 50) == (255, 0, 0, 255)
