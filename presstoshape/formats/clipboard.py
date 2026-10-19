"""PressToShape's own clipboard payload: a versioned JSON list of shapes, encoded like shapes in .p2s files.

Short-lived, so not migrated: a payload from another format version is refused and the paste falls back to the
SVG that is always on the clipboard next to it.
"""

import json
from collections.abc import Sequence

from presstoshape.formats.p2s import P2sError, decode_shape, encode_shape, read_int, read_list, read_object
from presstoshape.formats.p2s_migrations import CURRENT_VERSION
from presstoshape.models.shapes import Shape

MIME_TYPE = "application/x-presstoshape-shapes"
FORMAT_NAME = "presstoshape-shapes"
MAX_BYTES = 64 * 1024 * 1024


class ClipboardError(P2sError):
    """Clipboard data that can't be pasted as PressToShape shapes."""


def encode_shapes(shapes: Sequence[Shape]) -> bytes:
    payload = {
        "format": FORMAT_NAME,
        "version": CURRENT_VERSION,
        "shapes": [encode_shape(shape) for shape in shapes],
    }
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _reject_constant(name: str) -> None:
    raise ClipboardError(f"clipboard data contains {name}")


def decode_shapes(data: bytes) -> list[Shape]:
    """Shapes bottom to top with their stored ids; raises ClipboardError for anything else."""
    if len(data) > MAX_BYTES:
        raise ClipboardError("clipboard data is too large")
    try:
        payload = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ClipboardError(f"clipboard data isn't valid JSON ({error})") from None
    try:
        payload = read_object(payload, "clipboard")
        if payload.get("format") != FORMAT_NAME:
            raise ClipboardError("not PressToShape clipboard data")
        version = read_int(payload.get("version"), "clipboard.version", minimum=1)
        if version != CURRENT_VERSION:
            raise ClipboardError(f"clipboard data has format {version}, this version uses {CURRENT_VERSION}")
        items = read_list(payload.get("shapes"), "clipboard.shapes")
        if not items:
            raise ClipboardError("clipboard data holds no shapes")
        return [decode_shape(item, f"clipboard.shapes[{index}]") for index, item in enumerate(items)]
    except ClipboardError:
        raise
    except P2sError as error:
        raise ClipboardError(str(error)) from None
