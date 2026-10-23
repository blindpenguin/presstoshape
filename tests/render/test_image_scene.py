import skia

from presstoshape.formats.image_info import probe
from presstoshape.geometry import affine
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import Aspect, GroupShape, ImageShape, Masking, RectShape, Style
from presstoshape.render.export import render_png
from presstoshape.render.handles import selection_frame
from presstoshape.render.hit_test import shape_at, shapes_in_rect
from presstoshape.render.paths import PathCache
from presstoshape.render.picture import DocumentPicture
from presstoshape.render.scene import REFERENCE_OPACITY, draw_document
from presstoshape.tools.snapper import shape_points

SIZE = 100
CLEAR = (0, 0, 0, 0)


def encoded(width, height):
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorRED)
    canvas.drawRect(skia.Rect.MakeXYWH(width / 2, 0, width / 2, height), skia.Paint(Color=skia.ColorBLUE))
    return surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100).bytes()


WIDE = probe(encoded(40, 20))


def image(shape_id=1, x=0, y=0, width=100, height=100, **fields):
    return ImageShape(shape_id, x, y, width, height, fields.pop("data", WIDE), **fields)


def document(*shapes):
    return Document(SIZE, SIZE, [Layer("L", True, list(shapes))])


def render(*shapes, **fields):
    surface = skia.Surface(SIZE, SIZE)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    draw_document(surface.getCanvas(), document(*shapes), PathCache(), **fields)
    return surface


def pixel(surface, x, y):
    return tuple(int(v) for v in surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x])


def test_image_is_drawn_into_the_letterboxed_area():
    surface = render(image())
    assert pixel(surface, 20, 50) == (255, 0, 0, 255)
    assert pixel(surface, 80, 50) == (0, 0, 255, 255)
    assert pixel(surface, 50, 10) == CLEAR


def test_hidden_image_is_not_drawn():
    assert pixel(render(image(hidden=True)), 20, 50) == CLEAR


def test_hit_test_and_bounds_use_the_drawn_area():
    cache = PathCache()
    shape = image()
    assert shape_at([shape], cache, (50, 50), 0.0) == 1
    assert shape_at([shape], cache, (50, 10), 0.0) is None
    bounds = cache.bounds(shape)
    assert (bounds.left(), bounds.top(), bounds.width(), bounds.height()) == (0, 25, 100, 50)
    assert shapes_in_rect([shape], cache, (0, 0, 100, 20)) == set()
    assert shapes_in_rect([shape], cache, (0, 0, 100, 30)) == {1}


def test_selection_frame_uses_the_viewport_box():
    frame = selection_frame([image()], PathCache())
    assert frame.rect == (0, 0, 100, 100)


def test_snap_points_are_the_corners_of_the_drawn_area():
    points = set(shape_points(image()))
    assert {(0, 25), (100, 25), (100, 75), (0, 75)} <= points


def test_rotation_turns_the_picture():
    shape = image(width=100, height=40, data=probe(encoded(100, 40)), transform=affine.rotation(1.5707963, 50, 20))
    surface = render(shape)
    assert pixel(surface, 50, 10)[0] > 200 or pixel(surface, 50, 60)[0] > 200


def test_opacity_is_applied():
    alpha = pixel(render(image(opacity=0.5)), 20, 50)[3]
    assert 125 <= alpha <= 130


def test_group_opacity_applies_to_the_image():
    alpha = pixel(render(GroupShape(9, (image(),), opacity=0.5)), 20, 50)[3]
    assert 125 <= alpha <= 130


def test_reference_is_dimmed_and_left_out_on_request():
    shape = image(reference=True, locked=True)
    alpha = pixel(render(shape), 20, 50)[3]
    assert abs(alpha - round(255 * REFERENCE_OPACITY)) <= 3
    assert pixel(render(shape, references=False), 20, 50) == CLEAR
    nested = GroupShape(9, (shape,))
    assert pixel(render(nested, references=False), 20, 50) == CLEAR


def test_export_skips_references():
    png = render_png(document(image(1, reference=True, locked=True)), 1.0)
    surface = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(png))
    assert surface.toarray(colorType=skia.kRGBA_8888_ColorType)[50, 20][3] == 0


def test_reference_is_not_hit_or_band_selected():
    cache = PathCache()
    shape = image(reference=True)
    assert shape_at([shape], cache, (50, 50), 0.0) is None
    assert shapes_in_rect([shape], cache, (0, 0, 100, 100)) == set()
    assert shape_at([GroupShape(9, (shape,))], cache, (50, 50), 0.0) is None


def test_image_inside_a_clip_is_clipped():
    clip = RectShape(2, 0, 0, 40, 100, Style(fill="#000000", stroke=None))
    group = GroupShape(9, (image(), clip), masking=Masking("clip", (2,)))
    surface = render(group)
    assert pixel(surface, 20, 50) == (255, 0, 0, 255)
    assert pixel(surface, 80, 50) == CLEAR


def test_image_inside_a_luminance_mask_is_masked():
    white = RectShape(2, 0, 0, 40, 100, Style(fill="#ffffff", stroke=None))
    group = GroupShape(9, (image(), white), masking=Masking("luminance", (2,)))
    surface = render(group)
    assert pixel(surface, 20, 50) == (255, 0, 0, 255)
    assert pixel(surface, 80, 50) == CLEAR


def test_picture_replay_reuses_the_decoded_image():
    cache = PathCache()
    picture = DocumentPicture(cache)
    doc = document(image())
    surface = skia.Surface(SIZE, SIZE)
    for _frame in range(3):
        picture.draw(surface.getCanvas(), doc)
    assert pixel(surface, 20, 50) == (255, 0, 0, 255)
    assert cache.images.decoded_bytes == 40 * 20 * 4


def test_gesture_matrix_moves_the_image_without_re_recording():
    cache = PathCache()
    picture = DocumentPicture(cache)
    doc = document(image(width=50, height=50, aspect=Aspect("none")))
    surface = skia.Surface(SIZE, SIZE)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    picture.draw(surface.getCanvas(), doc, frozenset({1}), affine.translation(40, 0))
    assert pixel(surface, 60, 20) == (255, 0, 0, 255)
    assert pixel(surface, 10, 20) == CLEAR
    key = picture._key
    picture.draw(surface.getCanvas(), doc, frozenset({1}), affine.translation(20, 0))
    assert picture._key == key


def test_zoom_changes_the_recorded_sampling():
    picture = DocumentPicture(PathCache())
    doc = document(image(width=40, height=20, aspect=Aspect("none")))
    surface = skia.Surface(SIZE, SIZE)
    canvas = surface.getCanvas()
    picture.draw(canvas, doc)
    smooth = picture._key
    canvas.save()
    canvas.scale(4, 4)
    picture.draw(canvas, doc)
    canvas.restore()
    assert picture._key != smooth


def test_document_without_images_pays_nothing_extra():
    picture = DocumentPicture(PathCache())
    doc = document(RectShape(1, 0, 0, 10, 10, Style(fill="#000000", stroke=None)))
    surface = skia.Surface(SIZE, SIZE)
    canvas = surface.getCanvas()
    picture.draw(canvas, doc)
    key = picture._key
    canvas.scale(3, 3)
    picture.draw(canvas, doc)
    assert picture._key == key
