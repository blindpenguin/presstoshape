import json
import math

import pytest

from presstoshape.formats import clipboard
from presstoshape.formats.clipboard import ClipboardError, decode_shapes, encode_shapes
from presstoshape.formats.p2s_migrations import CURRENT_VERSION
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    GradientStop,
    LinearGradient,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)

RED = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
OUTLINE = Style(fill=None, stroke="#18181b", stroke_width=1.25)
ROTATED = (math.cos(0.3), math.sin(0.3), -math.sin(0.3), math.cos(0.3), 12.5, -3.0)


def _sample_shapes():
    inner = CompositeShape(
        20, (RectShape(21, 0, 0, 40, 40, RED), EllipseShape(22, 40, 40, 15, 15, RED)), ("add", "exclude"), RED
    )
    composite = CompositeShape(
        10, (RectShape(11, 0.1, 0.2, 100, 60, Style()), inner), ("add", "subtract"), Style(fill="#00aa00")
    )
    path = PathShape(3, (MoveTo(0, 0), LineTo(10.000000001, 0), CubicTo(1, 2, 3, 4, 5, 6), Close()), OUTLINE)
    return [
        RectShape(1, -5, 1e-9, 30, 20, Style(), ROTATED),
        EllipseShape(2, 5, 5, 3, 4, OUTLINE),
        path,
        TextShape(4, 10, 20, 'Hi "there" ☺', 18.5, RED, ROTATED),
        composite,
    ]


def _payload(**changes) -> bytes:
    payload = json.loads(encode_shapes(_sample_shapes()))
    payload.update(changes)
    return json.dumps(payload).encode()


def test_shapes_round_trip_exactly_in_order():
    shapes = _sample_shapes()
    assert decode_shapes(encode_shapes(shapes)) == shapes


def test_payload_names_format_and_version():
    payload = json.loads(encode_shapes(_sample_shapes()))
    assert payload["format"] == "presstoshape-shapes"
    assert payload["version"] == CURRENT_VERSION


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"\xff\xfe",
        b"[]",
        b'{"format": "presstoshape-shapes", "version": 1, "shapes": [{"type": "rect", "x": NaN}]}',
        _payload(format="something-else"),
        _payload(version=CURRENT_VERSION + 1),
        _payload(version="1"),
        _payload(shapes=[]),
        _payload(shapes="none"),
        _payload(shapes=[{"type": "hexagon", "id": 1, "style": {}}]),
    ],
)
def test_rejects_unusable_data(data):
    with pytest.raises(ClipboardError):
        decode_shapes(data)


def test_rejects_oversized_data(monkeypatch):
    monkeypatch.setattr(clipboard, "MAX_BYTES", 10)
    with pytest.raises(ClipboardError, match="too large"):
        decode_shapes(encode_shapes(_sample_shapes()))


def test_gradients_survive_copy_and_paste():
    gradient = LinearGradient(
        0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff", 0.5)), spread="repeat"
    )
    shapes = [RectShape(1, 0, 0, 10, 10, Style(fill=gradient, stroke=gradient))]
    assert decode_shapes(encode_shapes(shapes)) == shapes


def test_masked_groups_survive_the_clipboard():
    from presstoshape.models.shapes import GroupShape, Masking

    group = GroupShape(
        5, (RectShape(1, 0, 0, 10, 10, RED), EllipseShape(2, 5, 5, 3, 3, RED)), masking=Masking("clip", (2,), True)
    )
    assert decode_shapes(encode_shapes([group])) == [group]


def test_pictures_travel_with_the_shapes_and_share_one_blob():
    from presstoshape.formats.clipboard import decode_shapes_with_notes
    from presstoshape.models.shapes import GroupShape, ImageShape
    from tests.helpers import tiny_image

    picture = tiny_image()
    shapes = [
        ImageShape(1, 0.0, 0.0, 20.0, 10.0, picture),
        GroupShape(3, (ImageShape(2, 5.0, 5.0, 8.0, 8.0, picture, opacity=0.5),)),
    ]
    data = encode_shapes(shapes)
    assert len(json.loads(data)["media"]) == 1
    restored, notes = decode_shapes_with_notes(data)
    assert restored == shapes and notes == []
    assert restored[0].data is restored[1].children[0].data
    assert restored[0].data.data == picture.data


def test_pictures_over_the_size_cap_paste_as_placeholders_with_a_note(monkeypatch):
    from presstoshape.formats import clipboard
    from presstoshape.formats.clipboard import decode_shapes_with_notes
    from presstoshape.formats.p2s import MISSING_MIME
    from presstoshape.models.shapes import ImageShape
    from tests.helpers import tiny_image

    monkeypatch.setattr(clipboard, "MAX_MEDIA_BYTES", 10)
    data = encode_shapes([ImageShape(1, 0.0, 0.0, 20.0, 10.0, tiny_image())])
    assert "media" not in json.loads(data)
    (shape,), notes = decode_shapes_with_notes(data)
    assert shape.data.mime == MISSING_MIME and len(notes) == 1


def test_a_picture_that_is_not_what_its_digest_says_pastes_as_a_placeholder():
    from presstoshape.formats.clipboard import decode_shapes_with_notes
    from presstoshape.formats.p2s import MISSING_MIME
    from presstoshape.models.shapes import ImageShape
    from tests.helpers import tiny_image

    payload = json.loads(encode_shapes([ImageShape(1, 0.0, 0.0, 20.0, 10.0, tiny_image())]))
    (digest,) = payload["media"]
    payload["media"][digest] = "AAAA"
    (shape,), notes = decode_shapes_with_notes(json.dumps(payload).encode())
    assert shape.data.mime == MISSING_MIME and notes


def test_corner_nodes_survive_the_clipboard():
    path = PathShape(1, (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 0, corner=True), LineTo(30, 0)), Style())
    assert decode_shapes(encode_shapes([path])) == [path]
