"""Pictures of SVG `<image>` elements: where their bytes come from and which of them are accepted.

Nothing is ever fetched over a network. Data URIs and files on this computer are read, after the checks that
keep a hostile file from using up memory or reading special files: sizes are known before bytes are read, only
regular files are opened, and one picture used by many elements is read and kept once.
"""

import base64
import binascii
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote_to_bytes, urlsplit
from urllib.request import url2pathname

from presstoshape.formats.image_info import MAX_BYTES, ImageError, probe
from presstoshape.formats.svg_notes import Note, NoteCollector
from presstoshape.models.shapes import ImageData

MAX_IMPORT_BYTES = 256 * 1024 * 1024
_READ_CHUNK = 1024 * 1024
# base64 text for MAX_BYTES of data, with room for line breaks.
_MAX_BASE64_CHARS = MAX_BYTES // 3 * 4 + 4 + MAX_BYTES // 40
_SVG_START = re.compile(rb"\s*(?:<\?xml|<svg|<!DOCTYPE\s+svg)", re.IGNORECASE)


@dataclass
class ImageBudget:
    """What one import has read so far: the bytes kept (capped), and every picture by source and by digest, so a
    file referenced 10 000 times is read and embedded once. Failures are remembered too."""

    remaining: int = MAX_IMPORT_BYTES
    by_source: dict[str, ImageData | Note] = field(default_factory=dict)
    by_digest: dict[str, ImageData] = field(default_factory=dict)


def load_image(
    href: str | None, base_folder: Path | None, budget: ImageBudget, notes: NoteCollector
) -> ImageData | None:
    """The picture `href` names, or None after counting why not in `notes`. Never raises."""
    if href is None or not href.strip():
        notes.add(Note.IMAGE_MISSING)
        return None
    href = href.strip()
    # A relative name means a different file in a different folder (`xml:base`).
    key = href if href[:5].lower() == "data:" else f"{base_folder}\0{href}"
    result = budget.by_source.get(key)
    if result is None:
        result = _load(href, base_folder, budget)
        budget.by_source[key] = result
    if isinstance(result, Note):
        notes.add(result)
        return None
    return result


def _load(href: str, base_folder: Path | None, budget: ImageBudget) -> ImageData | Note:
    if href[:5].lower() == "data:":
        data = _data_uri(href)
    else:
        data = _file(href, base_folder, budget)
    if isinstance(data, Note):
        return data
    return _accept(data, budget)


def _accept(raw: bytes, budget: ImageBudget) -> ImageData | Note:
    if _SVG_START.match(raw[:256]):
        return Note.IMAGE_SVG
    try:
        probed = probe(raw)
    except ImageError as error:
        return Note.IMAGE_TOO_LARGE if error.reason in ("too_large", "too_many_pixels") else Note.IMAGE_UNSUPPORTED
    known = budget.by_digest.get(probed.digest)
    if known is not None:
        return known
    if len(raw) > budget.remaining:
        return Note.IMAGE_TOO_LARGE
    budget.remaining -= len(raw)
    budget.by_digest[probed.digest] = probed
    return probed


def _data_uri(href: str) -> bytes | Note:
    header, comma, payload = href[5:].partition(",")
    if not comma:
        return Note.IMAGE_UNSUPPORTED
    parameters = [part.strip().lower() for part in header.split(";")]
    if parameters[0] == "image/svg+xml":
        return Note.IMAGE_SVG
    if "base64" in parameters[1:]:
        if len(payload) > _MAX_BASE64_CHARS:
            return Note.IMAGE_TOO_LARGE
        text = "".join(payload.split())
        try:
            return base64.b64decode(text + "=" * (-len(text) % 4), validate=True)
        except (binascii.Error, ValueError):
            return Note.IMAGE_UNSUPPORTED
    if len(payload) > MAX_BYTES * 3:
        return Note.IMAGE_TOO_LARGE
    return unquote_to_bytes(payload)


def _local_path(href: str, base_folder: Path | None) -> Path | Note:
    parts = urlsplit(href)
    scheme = parts.scheme.lower()
    if len(scheme) == 1:
        return Path(href)
    if (
        scheme not in ("", "file")
        or (parts.netloc not in ("", "localhost") and scheme == "file")
        or (scheme == "" and parts.netloc)
    ):
        return Note.IMAGE_REMOTE
    if scheme == "file":
        path = Path(url2pathname(parts.path))
    else:
        path = Path(unquote_to_bytes(parts.path).decode("utf-8", "replace"))
    if path.is_absolute():
        return path
    return Note.IMAGE_MISSING if base_folder is None else base_folder / path


def _file(href: str, base_folder: Path | None, budget: ImageBudget) -> bytes | Note:
    path = _local_path(href, base_folder)
    if isinstance(path, Note):
        return path
    try:
        resolved = path.resolve(strict=True)
        descriptor = os.open(resolved, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    except (OSError, RuntimeError, ValueError):
        return Note.IMAGE_MISSING
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            return Note.IMAGE_MISSING
        if info.st_size > min(MAX_BYTES, budget.remaining):
            return Note.IMAGE_TOO_LARGE
        chunks, total = [], 0
        while chunk := os.read(descriptor, _READ_CHUNK):
            total += len(chunk)
            if total > MAX_BYTES:
                return Note.IMAGE_TOO_LARGE
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError:
        return Note.IMAGE_MISSING
    finally:
        os.close(descriptor)


def box_size(width: float | None, height: float | None, data: ImageData) -> tuple[float, float] | None:
    """The viewport size of an `<image>` from its `width` and `height` (None = missing or `auto`): a missing side
    follows the other by the picture's ratio, both missing give the pixel size. A side of zero or less draws
    nothing (None)."""
    if (width is not None and width <= 0) or (height is not None and height <= 0):
        return None
    if width is None and height is None:
        return float(data.width), float(data.height)
    if width is None:
        return height * data.width / data.height, height
    if height is None:
        return width, width * data.height / data.width
    return width, height
