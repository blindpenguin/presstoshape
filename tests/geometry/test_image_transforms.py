import math

import pytest

from presstoshape.geometry import affine, transforms
from presstoshape.geometry.aspect import visible_box
from presstoshape.models.shapes import Aspect, ImageData, ImageShape

DATA = ImageData(b"x", 20, 10, "image/png", "ab" * 32)


def image(aspect=Aspect("xMidYMid"), **fields):
    return ImageShape(1, 10.0, 20.0, 40.0, 40.0, DATA, aspect, **fields)


def test_visible_box_per_aspect():
    assert visible_box(image()) == (10.0, 30.0, 40.0, 20.0)
    assert visible_box(image(Aspect("xMinYMin"))) == (10.0, 20.0, 40.0, 20.0)
    assert visible_box(image(Aspect("xMaxYMax"))) == (10.0, 40.0, 40.0, 20.0)
    assert visible_box(image(Aspect("none"))) == (10.0, 20.0, 40.0, 40.0)
    assert visible_box(image(Aspect("xMidYMid", True))) == (10.0, 20.0, 40.0, 40.0)


def test_visible_box_of_an_empty_viewport_is_empty():
    shape = ImageShape(1, 5.0, 6.0, 0.0, 10.0, DATA)
    assert visible_box(shape) == (5.0, 6.0, 0.0, 10.0)


def test_outline_is_the_visible_box_with_the_transform():
    shape = image(transform=affine.translation(100, 0))
    xs = [segment.x for segment in transforms.outline(shape) if hasattr(segment, "x")]
    ys = [segment.y for segment in transforms.outline(shape) if hasattr(segment, "y")]
    assert (min(xs), max(xs), min(ys), max(ys)) == (110.0, 150.0, 30.0, 50.0)


def test_translate_keeps_box_aspect_and_data():
    moved = transforms.translate(image(Aspect("xMinYMax", True), opacity=0.5), 5.0, -5.0)
    assert (moved.x, moved.y, moved.width, moved.height) == (15.0, 15.0, 40.0, 40.0)
    assert (moved.aspect, moved.opacity, moved.data) == (Aspect("xMinYMax", True), 0.5, DATA)


def test_translate_conjugates_a_rotation_about_the_new_centre():
    turned = transforms.with_rotation(image(), 90.0)
    moved = transforms.translate(turned, 10.0, 0.0)
    assert transforms.rotation_of(moved) == pytest.approx(90.0)
    centre = affine.apply(moved.transform, moved.x + 20.0, moved.y + 20.0)
    assert centre == pytest.approx((moved.x + 20.0, moved.y + 20.0))


def test_scaling_changes_the_box_and_keeps_aspect():
    scaled = transforms.transform_shape(image(Aspect("xMinYMid")), affine.scaling(2.0, 2.0))
    assert (scaled.width, scaled.height) == (80.0, 80.0)
    assert scaled.aspect == Aspect("xMinYMid")
    assert scaled.transform == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_rotation_keeps_the_box():
    turned = transforms.transform_shape(image(), affine.rotation(math.radians(30), 30.0, 40.0))
    assert (turned.width, turned.height) == (pytest.approx(40.0), pytest.approx(40.0))
    assert transforms.rotation_of(turned) == pytest.approx(30.0)


def test_flip_mirrors_the_pixels_instead_of_folding_into_a_rotation():
    mirrored = transforms.transform_shape(image(), affine.compose(affine.translation(60, 0), affine.scaling(-1, 1)))
    left_edge = affine.apply(mirrored.transform, mirrored.x, mirrored.y)
    right_edge = affine.apply(mirrored.transform, mirrored.x + mirrored.width, mirrored.y)
    assert (left_edge[0], right_edge[0]) == (pytest.approx(50.0), pytest.approx(10.0))
    twice = transforms.transform_shape(mirrored, affine.compose(affine.translation(60, 0), affine.scaling(-1, 1)))
    assert twice.transform == pytest.approx((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))


def test_a_singular_transform_is_refused():
    with pytest.raises(ValueError):
        transforms.transform_shape(image(), affine.scaling(0.0, 1.0))


def test_stretching_a_letterboxed_picture_bakes_the_drawn_area_and_stretches_it():
    shape = image()
    stretched = transforms.transform_shape(shape, affine.scaling(2.0, 0.5))
    assert stretched.aspect == Aspect("none")
    assert (stretched.x, stretched.y, stretched.width, stretched.height) == (20.0, 15.0, 80.0, 10.0)
    assert transforms.outline(stretched) is not None
    box = visible_box(stretched)
    assert box == (20.0, 15.0, 80.0, 10.0)


def test_stretching_a_sliced_picture_keeps_the_matrix_so_the_clip_follows():
    shape = image(Aspect("xMidYMid", True))
    stretched = transforms.transform_shape(shape, affine.scaling(2.0, 0.5))
    assert stretched.aspect == Aspect("xMidYMid", True)
    assert (stretched.width, stretched.height) == (40.0, 40.0)
    assert stretched.transform == (2.0, 0.0, 0.0, 0.5, 0.0, 0.0)


def test_uniform_scaling_keeps_the_fit():
    scaled = transforms.transform_shape(image(Aspect("xMinYMax")), affine.scaling(2.0, 2.0))
    assert scaled.aspect == Aspect("xMinYMax") and (scaled.width, scaled.height) == (80.0, 80.0)


def test_stretching_a_rotated_picture_keeps_the_drawn_result():
    turned = transforms.with_rotation(image(), 90.0)
    scale = affine.scaling(3.0, 1.0)
    expected = [affine.apply(scale, *affine.apply(turned.transform, x, y)) for x, y in ((10, 30), (50, 50))]
    stretched = transforms.transform_shape(turned, scale)
    box_x, box_y, box_w, box_h = visible_box(stretched)
    got = [
        affine.apply(stretched.transform, box_x, box_y),
        affine.apply(stretched.transform, box_x + box_w, box_y + box_h),
    ]
    xs = sorted(point[0] for point in got)
    assert xs[1] - xs[0] == pytest.approx(abs(expected[1][0] - expected[0][0]))
