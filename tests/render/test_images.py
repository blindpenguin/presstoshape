import struct

import pytest
import skia

from presstoshape.formats.image_info import probe
from presstoshape.models.shapes import Aspect, ImageData, ImageShape
from presstoshape.render import images
from presstoshape.render.images import ImageCache, draw_image, draw_placeholder, trial_decode

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
CLEAR = (0, 0, 0, 0)


def encoded(width, height, left=skia.ColorRED, right=skia.ColorBLUE, format=skia.EncodedImageFormat.kPNG):
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(left)
    canvas.drawRect(skia.Rect.MakeXYWH(width / 2, 0, width / 2, height), skia.Paint(Color=right))
    return surface.makeImageSnapshot().encodeToData(format, 100).bytes()


def png(width=20, height=10, **colors):
    return probe(encoded(width, height, **colors))


def shape(data, x=0, y=0, width=10, height=10, aspect=Aspect("xMidYMid"), opacity=1.0):
    return ImageShape(1, x, y, width, height, data, aspect, opacity)


def canvas_for(width=10, height=10):
    surface = skia.Surface(width, height)
    return surface, surface.getCanvas()


def _rgba(surface, x, y):
    info = skia.ImageInfo.Make(1, 1, skia.kRGBA_8888_ColorType, skia.kUnpremul_AlphaType)
    out = bytearray(4)
    assert surface.readPixels(info, out, 4, x, y)
    return tuple(out)


def draw(data, **fields):
    surface, canvas = canvas_for(fields.pop("surface_width", 10), fields.pop("surface_height", 10))
    cache = ImageCache()
    image_shape = shape(data, **fields)
    draw_image(canvas, image_shape, cache.get(data), image_shape.opacity)
    return surface


@pytest.mark.parametrize(
    "align, top_row",
    [("xMidYMid", 2), ("xMidYMin", 0), ("xMidYMax", 5)],
)
def test_meet_letterboxes_by_alignment(align, top_row):
    surface = draw(png(), aspect=Aspect(align))
    assert _rgba(surface, 2, top_row + 2) == RED
    assert _rgba(surface, 8, top_row + 2) == BLUE
    assert _rgba(surface, 5, 9 if top_row == 0 else 0) == CLEAR


def test_meet_none_stretches_to_the_viewport():
    surface = draw(png(), aspect=Aspect("none"))
    assert _rgba(surface, 2, 0) == RED and _rgba(surface, 8, 9) == BLUE


@pytest.mark.parametrize("align, colour", [("xMinYMid", RED), ("xMidYMid", None), ("xMaxYMid", BLUE)])
def test_slice_covers_the_viewport_and_crops_by_alignment(align, colour):
    surface = draw(png(), aspect=Aspect(align, True))
    assert all(_rgba(surface, x, y)[3] == 255 for x in (0, 9) for y in (0, 9))
    if colour is not None:
        assert _rgba(surface, 0, 5) == colour and _rgba(surface, 9, 5) == colour
    else:
        assert _rgba(surface, 2, 5) == RED and _rgba(surface, 8, 5) == BLUE


def test_slice_is_clipped_to_the_viewport():
    surface = draw(png(), x=2, y=2, width=6, height=6, aspect=Aspect("xMidYMid", True))
    assert _rgba(surface, 1, 5) == CLEAR and _rgba(surface, 8, 5) == CLEAR
    assert _rgba(surface, 3, 5)[3] == 255


def test_canvas_matrix_rotates_and_moves_the_picture():
    surface, canvas = canvas_for(10, 10)
    data = png(10, 10)
    canvas.translate(10, 0)
    canvas.rotate(90)
    draw_image(canvas, shape(data), ImageCache().get(data), 1.0)
    assert _rgba(surface, 5, 2) == RED
    assert _rgba(surface, 5, 8) == BLUE


def test_opacity_is_paint_alpha():
    surface = draw(png(10, 10), opacity=0.5)
    assert _rgba(surface, 2, 5)[3] in range(126, 130)


def test_zero_opacity_or_empty_viewport_draws_nothing():
    for fields in ({"opacity": 0.0}, {"width": 0}, {"height": 0}):
        surface = draw(png(), **fields)
        assert _rgba(surface, 5, 5) == CLEAR


def test_pixels_stay_square_at_high_zoom_and_smooth_when_less_magnified():
    data = probe(encoded(2, 1))
    surface, canvas = canvas_for(8, 4)
    canvas.scale(4, 4)
    draw_image(canvas, shape(data, width=2, height=1), ImageCache().get(data), 1.0)
    assert _rgba(surface, 3, 2) == RED and _rgba(surface, 4, 2) == BLUE

    surface, canvas = canvas_for(3, 1)
    canvas.scale(1.5, 1.5)
    draw_image(canvas, shape(data, width=2, height=1), ImageCache().get(data), 1.0)
    middle = _rgba(surface, 1, 0)
    assert middle not in (RED, BLUE) and middle[3] == 255


def test_placeholder_is_a_hairline_box_with_a_cross():
    surface, canvas = canvas_for(20, 20)
    draw_placeholder(canvas, skia.Rect.MakeXYWH(2, 2, 16, 16))
    assert _rgba(surface, 2, 10)[3] > 0 and _rgba(surface, 10, 2)[3] > 0
    assert _rgba(surface, 10, 10)[3] > 0
    assert _rgba(surface, 6, 12)[3] == 0


def test_corrupt_body_decodes_to_none_and_is_drawn_as_placeholder():
    good = encoded(8, 8)
    broken = probe(good[:30] + b"\x00" * 40)
    cache = ImageCache()
    assert cache.get(broken) is None
    assert not trial_decode(broken)
    surface, canvas = canvas_for()
    draw_image(canvas, shape(broken), cache.get(broken), 1.0)
    assert _rgba(surface, 0, 5)[3] > 0 and _rgba(surface, 5, 2)[3] == 0


def test_missing_blob_is_a_placeholder_not_an_error():
    missing = ImageData(b"", 4, 4, "application/x-missing", "0" * 64)
    assert ImageCache().get(missing) is None


def test_failed_decode_is_tried_once(monkeypatch):
    calls = []
    monkeypatch.setattr(images, "decode", lambda data: calls.append(data.digest))
    data = png()
    cache = ImageCache()
    assert cache.get(data) is None and cache.get(data) is None
    assert len(calls) == 1


def jpeg_with_orientation(orientation):
    jpeg = encoded(4, 2, format=skia.EncodedImageFormat.kJPEG)
    ifd = struct.pack("<H", 1) + struct.pack("<HHIHxx", 0x0112, 3, 1, orientation) + b"\0\0\0\0"
    body = b"Exif\0\0" + b"II" + struct.pack("<HI", 42, 8) + ifd
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body + jpeg[2:]


def test_exif_rotated_jpeg_is_upright_when_drawn():
    data = probe(jpeg_with_orientation(6))
    assert (data.width, data.height) == (2, 4)
    image = ImageCache().get(data)
    assert (image.width(), image.height()) == (2, 4)
    surface, canvas = canvas_for(2, 4)
    draw_image(canvas, shape(data, width=2, height=4), image, 1.0)
    top, bottom = _rgba(surface, 1, 0), _rgba(surface, 1, 3)
    assert top[0] > 200 and top[2] < 60
    assert bottom[2] > 200 and bottom[0] < 60


def blob(index):
    return probe(encoded(16, 16, left=0xFF000000 | index))


def test_least_recently_used_image_is_evicted_over_budget():
    first, second, third = blob(1), blob(2), blob(3)
    cache = ImageCache(budget_bytes=2 * 16 * 16 * 4)
    cache.get(first)
    cache.get(second)
    cache.get(first)
    cache.get(third)
    assert first.digest in cache and third.digest in cache
    assert second.digest not in cache
    assert cache.decoded_bytes <= 2 * 16 * 16 * 4


def test_an_image_bigger_than_the_budget_is_still_returned():
    cache = ImageCache(budget_bytes=1)
    data = blob(1)
    assert cache.get(data) is not None
    assert data.digest in cache


def test_huge_images_get_a_halved_copy_at_small_scale():
    data = probe(encoded(40, 40))
    cache = ImageCache(huge_pixels=100)
    full = cache.get(data, 1.0)
    assert (full.width(), full.height()) == (40, 40)
    assert cache.get(data, 0.6).width() == 40
    quarter = cache.get(data, 0.25)
    assert (quarter.width(), quarter.height()) == (10, 10)
    assert cache.get(data, 0.25) is quarter


def test_small_images_never_get_levels():
    data = probe(encoded(40, 40))
    assert ImageCache().get(data, 0.1).width() == 40


def test_evicting_an_image_drops_its_levels():
    data = probe(encoded(40, 40))
    cache = ImageCache(huge_pixels=100)
    cache.get(data, 0.25)
    cache.discard(data.digest)
    assert data.digest not in cache and cache.decoded_bytes == 0
