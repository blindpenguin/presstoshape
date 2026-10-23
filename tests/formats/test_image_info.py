import ast
import hashlib
import random
import struct
import zlib
from pathlib import Path

import pytest

from presstoshape.formats import image_info
from presstoshape.formats.image_info import MAX_BYTES, ImageError, probe


def png(width=7, height=5):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x10\x20\x30" * width for _row in range(height)) if width * height < 1000 else b""
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def exif(orientation, order="<"):
    ifd = struct.pack(order + "H", 1) + struct.pack(order + "HHIHxx", 0x0112, 3, 1, orientation) + b"\0\0\0\0"
    tiff = (b"II" if order == "<" else b"MM") + struct.pack(order + "HI", 42, 8) + ifd
    body = b"Exif\0\0" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body


def jpeg(width=7, height=5, orientation=None, order="<", exif_after=False):
    frame = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\x00"
    app = b"" if orientation is None else exif(orientation, order)
    scan = b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00" + b"\x00" * 4 + b"\xff\xd9"
    middle = frame + app if exif_after else app + frame
    return b"\xff\xd8\xff\xe0\x00\x04\x00\x00" + middle + scan


def gif(width=7, height=5):
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00;"


def webp_lossy(width=7, height=5):
    frame = b"\x10\x02\x00" + b"\x9d\x01\x2a" + struct.pack("<HH", width, height) + b"\x00" * 8
    return b"RIFF" + struct.pack("<I", 4 + 8 + len(frame)) + b"WEBP" + b"VP8 " + struct.pack("<I", len(frame)) + frame


def webp_lossless(width=7, height=5):
    bits = (width - 1) | ((height - 1) << 14)
    body = b"\x2f" + struct.pack("<I", bits) + b"\x00" * 8
    return b"RIFF" + struct.pack("<I", 4 + 8 + len(body)) + b"WEBP" + b"VP8L" + struct.pack("<I", len(body)) + body


def webp_extended(width=7, height=5):
    body = b"\x00\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    return b"RIFF" + struct.pack("<I", 4 + 8 + len(body)) + b"WEBP" + b"VP8X" + struct.pack("<I", len(body)) + body


SAMPLES = {
    "png": (png(), "image/png"),
    "jpeg": (jpeg(), "image/jpeg"),
    "gif": (gif(), "image/gif"),
    "webp lossy": (webp_lossy(), "image/webp"),
    "webp lossless": (webp_lossless(), "image/webp"),
    "webp extended": (webp_extended(), "image/webp"),
}


@pytest.mark.parametrize("name", SAMPLES)
def test_type_size_and_digest(name):
    data, mime = SAMPLES[name]
    info = probe(data)
    assert (info.mime, info.width, info.height) == (mime, 7, 5)
    assert info.digest == hashlib.sha256(data).hexdigest()
    assert info.data == data


@pytest.mark.parametrize("make", [png, jpeg, gif, webp_lossy, webp_lossless, webp_extended])
def test_large_sizes_are_read_exactly(make):
    info = probe(make(9000, 4001))
    assert (info.width, info.height) == (9000, 4001)


@pytest.mark.parametrize("order", ["<", ">"])
@pytest.mark.parametrize("exif_after", [False, True])
@pytest.mark.parametrize("orientation", range(1, 9))
def test_exif_orientation_swaps_size_for_5_to_8(orientation, order, exif_after):
    info = probe(jpeg(10, 4, orientation, order, exif_after))
    assert (info.width, info.height) == ((4, 10) if orientation >= 5 else (10, 4))


@pytest.mark.parametrize("orientation", [0, 9, 500])
def test_out_of_range_orientation_is_ignored(orientation):
    assert (probe(jpeg(10, 4, orientation)).width) == 10


def test_progressive_jpeg_frame_is_found():
    data = jpeg(10, 4).replace(b"\xff\xc0", b"\xff\xc2")
    assert (probe(data).width, probe(data).height) == (10, 4)


def test_empty_is_refused():
    with pytest.raises(ImageError) as caught:
        probe(b"")
    assert caught.value.reason == "empty"


@pytest.mark.parametrize(
    "data",
    [
        b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        b"II*\x00\x08\x00\x00\x00",
        b"MM\x00*\x00\x00\x00\x08",
        b"%PDF-1.7\n",
        b"BM" + b"\0" * 40,
        b"garbage",
        b"RIFF\0\0\0\0WAVE",
    ],
)
def test_other_types_are_unsupported(data):
    with pytest.raises(ImageError) as caught:
        probe(data)
    assert caught.value.reason == "unsupported"


@pytest.mark.parametrize("make", [png, jpeg, gif, webp_lossy])
@pytest.mark.parametrize("width, height", [(0, 5), (5, 0), (0, 0)])
def test_zero_dimensions_are_corrupt(make, width, height):
    with pytest.raises(ImageError) as caught:
        probe(make(width, height))
    assert caught.value.reason == "corrupt"


@pytest.mark.parametrize("make", [png, gif, jpeg, webp_extended])
def test_pixel_limit(make):
    with pytest.raises(ImageError) as caught:
        probe(make(10001, 10000))
    assert caught.value.reason == "too_many_pixels"
    assert probe(make(10000, 10000)).width == 10000


def test_huge_dimensions_do_not_allocate_or_hang():
    with pytest.raises(ImageError) as caught:
        probe(png(2**31, 2**31))
    assert caught.value.reason == "too_many_pixels"


def test_byte_limit_comes_before_anything_else():
    with pytest.raises(ImageError) as caught:
        probe(png() + b"\0" * MAX_BYTES)
    assert caught.value.reason == "too_large"


@pytest.mark.parametrize("name", SAMPLES)
def test_truncation_at_every_offset_only_raises_image_error(name):
    data, _mime = SAMPLES[name]
    for length in range(len(data)):
        try:
            probe(data[:length])
        except ImageError:
            pass


@pytest.mark.parametrize("name", SAMPLES)
def test_flipping_every_byte_only_raises_image_error(name):
    data, _mime = SAMPLES[name]
    for index in range(min(len(data), 120)):
        mutated = bytearray(data)
        mutated[index] ^= 0xFF
        try:
            probe(bytes(mutated))
        except ImageError:
            pass


def test_random_bytes_with_valid_signatures_only_raise_image_error():
    generator = random.Random(1234)
    signatures = [b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF89a", b"RIFF\0\0\0\0WEBP", b""]
    for _round in range(3000):
        data = generator.choice(signatures) + generator.randbytes(generator.randrange(0, 80))
        try:
            probe(data)
        except ImageError:
            pass


def test_truncated_files_are_corrupt_not_unsupported():
    for data in (png()[:20], jpeg()[:12], gif()[:8], webp_lossy()[:22]):
        with pytest.raises(ImageError) as caught:
            probe(data)
        assert caught.value.reason == "corrupt"


@pytest.mark.parametrize("reason", ["empty", "unsupported", "corrupt", "too_large", "too_many_pixels"])
def test_messages_name_the_file(reason):
    assert "photo.png" in ImageError(reason).message("photo.png")


def test_module_imports_neither_skia_nor_qt():
    tree = ast.parse(Path(image_info.__file__).read_text())
    imported = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not imported & {"skia", "PySide6", "PIL"}
