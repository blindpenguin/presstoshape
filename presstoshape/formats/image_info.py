"""Header-only look at an image file: type, pixel size and the limits, before anything decodes it.

Pure Python on purpose (no Skia, no Qt): the SVG reader, `.p2s` and the editor all need to know what a blob is
without paying for, or trusting, a decoder. Pixels are decoded lazily in `render/images.py`.
"""

import hashlib
import struct
from typing import Literal

from presstoshape.i18n import _
from presstoshape.models.shapes import ImageData

MAX_BYTES = 64 * 1024 * 1024
MAX_PIXELS = 100_000_000

Reason = Literal["empty", "unsupported", "corrupt", "too_large", "too_many_pixels"]

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG_MARKERS_WITHOUT_SIZE = {0x01, *range(0xD0, 0xDA)}
_JPEG_NOT_FRAMES = {0xC4, 0xC8, 0xCC}
_ORIENTATION_TAG = 0x0112


class ImageError(Exception):
    def __init__(self, reason: Reason):
        super().__init__(reason)
        self.reason = reason

    def message(self, name: str) -> str:
        match self.reason:
            case "empty":
                return _("{name}: the file is empty.").format(name=name)
            case "unsupported":
                return _("{name}: this is not a PNG, JPEG, WebP or GIF image.").format(name=name)
            case "corrupt":
                return _("{name}: the image is damaged.").format(name=name)
            case "too_large":
                return _("{name}: the file is larger than 64 MiB.").format(name=name)
            case _:
                return _("{name}: the image has more than 100 million pixels.").format(name=name)


def probe(data: bytes) -> ImageData:
    """Type, displayed size (EXIF orientation applied) and digest of an encoded image. Raises ImageError only."""
    if not data:
        raise ImageError("empty")
    if len(data) > MAX_BYTES:
        raise ImageError("too_large")
    try:
        mime, width, height = _header(data)
    except (struct.error, IndexError):
        raise ImageError("corrupt") from None
    if width <= 0 or height <= 0:
        raise ImageError("corrupt")
    if width * height > MAX_PIXELS:
        raise ImageError("too_many_pixels")
    return ImageData(bytes(data), width, height, mime, hashlib.sha256(data).hexdigest())


def _header(data: bytes) -> tuple[str, int, int]:
    if data.startswith(_PNG):
        return "image/png", *_png_size(data)
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", *_jpeg_size(data)
    if data[:6] in (b"GIF87a", b"GIF89a"):
        width, height = struct.unpack_from("<HH", data, 6)
        return "image/gif", width, height
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", *_webp_size(data)
    raise ImageError("unsupported")


def _png_size(data: bytes) -> tuple[int, int]:
    length, chunk = struct.unpack_from(">I4s", data, 8)
    if chunk != b"IHDR" or length < 8:
        raise ImageError("corrupt")
    return struct.unpack_from(">II", data, 16)


def _webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8 ":
        if data[23:26] != b"\x9d\x01\x2a":
            raise ImageError("corrupt")
        width, height = struct.unpack_from("<HH", data, 26)
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        if data[20] != 0x2F:
            raise ImageError("corrupt")
        (bits,) = struct.unpack_from("<I", data, 21)
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        if len(data) < 30:
            raise ImageError("corrupt")
        return width, height
    raise ImageError("corrupt")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    size: tuple[int, int] | None = None
    orientation = 1
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            raise ImageError("corrupt")
        marker = data[position + 1]
        if marker == 0xFF:
            position += 1
            continue
        if marker in _JPEG_MARKERS_WITHOUT_SIZE:
            position += 2
            continue
        (length,) = struct.unpack_from(">H", data, position + 2)
        if length < 2:
            raise ImageError("corrupt")
        body = position + 4
        end = position + 2 + length
        if 0xC0 <= marker <= 0xCF and marker not in _JPEG_NOT_FRAMES:
            height, width = struct.unpack_from(">HH", data, body + 1)
            size = (width, height)
        elif marker == 0xE1 and data[body : body + 6] == b"Exif\0\0":
            orientation = _exif_orientation(data[body + 6 : end])
        elif marker == 0xDA:
            break
        position = end
    if size is None:
        raise ImageError("corrupt")
    return (size[1], size[0]) if 5 <= orientation <= 8 else size


def _exif_orientation(tiff: bytes) -> int:
    """The orientation tag of the first IFD, 1 when absent or unreadable."""
    try:
        order = {b"II": "<", b"MM": ">"}[tiff[:2]]
        (first,) = struct.unpack_from(order + "I", tiff, 4)
        (count,) = struct.unpack_from(order + "H", tiff, first)
        for index in range(min(count, 64)):
            tag, kind, _items = struct.unpack_from(order + "HHI", tiff, first + 2 + index * 12)
            if tag == _ORIENTATION_TAG and kind == 3:
                (value,) = struct.unpack_from(order + "H", tiff, first + 2 + index * 12 + 8)
                return value if 1 <= value <= 8 else 1
    except (struct.error, KeyError):
        pass
    return 1
