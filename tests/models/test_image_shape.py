import dataclasses
import math

import pytest

from presstoshape.models.shapes import (
    Aspect,
    GroupShape,
    ImageData,
    ImageShape,
    children_of,
    sanitized_image,
    valid_digest,
)

DIGEST = "ab" * 32


def image_data(data=b"png-bytes", digest=DIGEST, width=4, height=3):
    return ImageData(data, width, height, "image/png", digest)


def image(**fields):
    return ImageShape(**{"id": 1, "x": 0.0, "y": 0.0, "width": 40.0, "height": 30.0, "data": image_data(), **fields})


def test_defaults_match_svg():
    shape = image()
    assert shape.aspect == Aspect("xMidYMid")
    assert (shape.opacity, shape.reference, shape.hidden, shape.locked) == (1.0, False, False, False)
    assert shape.transform == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_shape_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        image().x = 3.0


def test_image_data_equality_and_hash_follow_the_digest():
    first = image_data(b"one", DIGEST)
    same = image_data(b"other bytes", DIGEST)
    different = image_data(b"one", "cd" * 32)
    assert first == same and hash(first) == hash(same)
    assert first != different


def test_replace_shares_the_blob():
    shape = image()
    moved = dataclasses.replace(shape, x=5.0)
    assert moved.data is shape.data


def test_image_is_a_leaf():
    assert children_of(image()) == ()
    assert children_of(GroupShape(2, (image(),))) == (image(),)


def test_sanitized_clamps_size_opacity_and_alignment():
    clean = sanitized_image(image(width=-3.0, height=math.inf, x=math.nan, opacity=4.0, aspect=Aspect("middle", True)))
    assert (clean.x, clean.width, clean.height, clean.opacity) == (0.0, 0.0, 0.0, 1.0)
    assert clean.aspect == Aspect("xMidYMid")


def test_sanitized_leaves_a_clean_shape_alone():
    shape = image(aspect=Aspect("xMinYMax", True), opacity=0.5)
    assert sanitized_image(shape) == shape


def test_none_never_slices():
    assert sanitized_image(image(aspect=Aspect("none", True))).aspect == Aspect("none")


def test_empty_size_is_legal():
    shape = sanitized_image(image(width=0.0, height=0.0))
    assert (shape.width, shape.height) == (0.0, 0.0)


@pytest.mark.parametrize("digest", [DIGEST, "0" * 64])
def test_valid_digest(digest):
    assert valid_digest(digest)


@pytest.mark.parametrize("digest", ["", "AB" * 32, "ab" * 31, "ab" * 33, "../" + "a" * 61, "g" * 64])
def test_invalid_digest(digest):
    assert not valid_digest(digest)


def test_geometry_helpers_treat_the_image_like_a_rect():
    from presstoshape.geometry import affine, transforms

    moved = transforms.translate(image(), 5.0, 6.0)
    assert (moved.x, moved.y, moved.width) == (5.0, 6.0, 40.0)
    scaled = transforms.transform_shape(image(), affine.scaling(2.0, 2.0))
    assert (scaled.width, scaled.height, scaled.aspect) == (80.0, 60.0, Aspect("xMidYMid"))
    turned = transforms.with_rotation(image(), 30.0)
    assert transforms.rotation_of(turned) == pytest.approx(30.0)
