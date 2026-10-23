"""PressToShape's own clipboard payload: a versioned JSON list of shapes, encoded like shapes in .p2s files.

Short-lived, so not migrated: a payload from another format version is refused and the paste falls back to the
SVG that is always on the clipboard next to it. Pictures travel in a `media` table (digest to base64), written
once per distinct picture.
"""

import base64
import binascii
import json
from collections.abc import Sequence

from presstoshape.formats.image_info import ImageError, probe
from presstoshape.formats.p2s import (
    MediaTable,
    P2sError,
    decode_shape,
    encode_shape,
    media_of,
    read_int,
    read_list,
    read_object,
)
from presstoshape.formats.p2s_migrations import CURRENT_VERSION
from presstoshape.i18n import _
from presstoshape.models.shapes import ImageData, Shape

MIME_TYPE = "application/x-presstoshape-shapes"
FORMAT_NAME = "presstoshape-shapes"
MAX_MEDIA_BYTES = 128 * 1024 * 1024
MAX_BYTES = 192 * 1024 * 1024


class ClipboardError(P2sError):
    """Clipboard data that can't be pasted as PressToShape shapes."""


def encode_shapes(shapes: Sequence[Shape]) -> bytes:
    """Pictures beyond `MAX_MEDIA_BYTES` in total are left out of the payload: they paste as placeholders, with a
    note."""
    payload = {
        "format": FORMAT_NAME,
        "version": CURRENT_VERSION,
        "shapes": [encode_shape(shape) for shape in shapes],
    }
    media = media_of(shapes)
    if media and sum(len(data.data) for data in media.values()) <= MAX_MEDIA_BYTES:
        payload["media"] = {digest: base64.b64encode(data.data).decode("ascii") for digest, data in media.items()}
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _reject_constant(name: str) -> None:
    raise ClipboardError(f"clipboard data contains {name}")


def _blob(media: dict, digest: str) -> ImageData | None:
    """The picture of `digest` from the payload's table, None when absent, undecodable or not what it claims."""
    text = media.get(digest)
    if not isinstance(text, str):
        return None
    try:
        data = probe(base64.b64decode(text, validate=True))
    except (binascii.Error, ValueError, ImageError):
        return None
    return data if data.digest == digest else None


def decode_shapes(data: bytes) -> list[Shape]:
    """Shapes bottom to top with their stored ids; raises ClipboardError for anything else."""
    return decode_shapes_with_notes(data)[0]


def decode_shapes_with_notes(data: bytes) -> tuple[list[Shape], list[str]]:
    """`decode_shapes` plus a note when pictures could not come along (too large to copy, damaged)."""
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
        table = read_object(payload.get("media", {}), "clipboard.media")
        media = MediaTable(lambda digest: _blob(table, digest))
        shapes = [decode_shape(item, f"clipboard.shapes[{index}]", media) for index, item in enumerate(items)]
        return shapes, [_("A picture could not be copied and shows as a placeholder.")] if media.notes else []
    except ClipboardError:
        raise
    except P2sError as error:
        raise ClipboardError(str(error)) from None
