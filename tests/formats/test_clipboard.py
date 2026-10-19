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
