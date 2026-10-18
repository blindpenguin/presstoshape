import skia

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Document, Layer
from veccy.models.shapes import RectShape, Style
from veccy.render.export import MAX_SIDE, export_size, render_png


def _doc() -> Document:
    return Document(100, 50, [Layer("L", True, [RectShape(1, 10, 10, 20, 20, Style(fill="#ff0000", stroke=None))])])


def _decode(data: bytes) -> skia.Image:
    return skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))


def _rgba(image: skia.Image, x: int, y: int) -> tuple[int, ...]:
    return tuple(int(v) for v in image.toarray(colorType=skia.kRGBA_8888_ColorType)[y, x])


def test_export_size_scales_and_rounds_up():
    assert export_size(_doc(), 1) == (100, 50)
    assert export_size(_doc(), 2) == (200, 100)
    assert export_size(_doc(), 0.333) == (34, 17)


def test_png_has_scaled_size_transparent_background_and_content():
    image = _decode(render_png(_doc(), 2))
    assert (image.width(), image.height()) == (200, 100)
    assert _rgba(image, 0, 0) == (0, 0, 0, 0)
    assert _rgba(image, 40, 40) == (255, 0, 0, 255)


def test_hidden_layers_are_not_exported():
    doc = _doc()
    doc.layers[0].visible = False
    assert _rgba(_decode(render_png(doc, 1)), 20, 20) == (0, 0, 0, 0)


def test_oversized_export_is_rejected():
    assert render_png(_doc(), MAX_SIDE) is None


def test_controller_export_writes_file_without_touching_undo(tmp_path):
    c = AppController(AppState())
    c.add_rectangle((0, 0), (50, 50))
    c.state.dirty = False
    undo_depth = len(c._undo_stack)
    calls = []
    c.subscribe(lambda: calls.append(1))
    target = tmp_path / "out.png"
    assert c.export_png(str(target), 1.5)
    assert _decode(target.read_bytes()).width() == 900
    assert c.state.export.scale == 1.5
    assert c.state.status_message == "Exported out.png (900 × 600 px)"
    assert not c.state.dirty
    assert len(c._undo_stack) == undo_depth
    assert calls == [1]


def test_controller_export_failure_reports_status(tmp_path):
    c = AppController(AppState())
    assert not c.export_png(str(tmp_path / "missing" / "out.png"), 1)
    assert c.state.status_message.startswith("Export failed")
