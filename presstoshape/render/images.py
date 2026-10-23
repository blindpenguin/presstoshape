"""Pictures on the canvas: decoding once per blob, drawing into the fitted rectangle, the stand-in for blobs that
won't decode.

An `ImageShape` has a viewport box (x, y, width, height), as SVG `<image>`. For an image read from SVG with
`meet` and a different aspect, the picture (and so the pickable and exported area) is smaller than the box; the
transform handles use the box, because scaling changes exactly those four numbers. For every image placed in the
editor the two coincide.
"""

import math
from collections import OrderedDict

import skia

from presstoshape.geometry.aspect import fitted_rect, visible_box
from presstoshape.models.shapes import ImageData, ImageShape

DEFAULT_BUDGET_BYTES = 256 * 1024 * 1024
HUGE_PIXELS = 16_000_000
_MAX_LEVEL = 8
# From this many screen pixels per image pixel on, pixels are shown as squares instead of smoothed.
_NEAREST_SCALE = 2.0
_MIP_BELOW_SCALE = 0.5
_PLACEHOLDER_COLOR = 0xFF9CA3AF

_NEAREST = skia.SamplingOptions(skia.FilterMode.kNearest, skia.MipmapMode.kNone)
_SMOOTH = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)

_Key = tuple[str, int]


def decode(data: ImageData) -> skia.Image | None:
    """The pixels of `data` as a raster image (EXIF orientation applied by Skia), None when it won't decode."""
    if not data.data:
        return None
    image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data.data))
    return None if image is None else image.makeRasterImage()


def trial_decode(data: ImageData) -> bool:
    return decode(data) is not None


def device_scale(canvas: skia.Canvas) -> float:
    matrix = canvas.getTotalMatrix()
    return math.hypot(matrix.getScaleX(), matrix.getSkewY())


class ImageCache:
    """Decoded images by blob digest, least recently used evicted beyond `budget_bytes` (decoded size). A blob
    that fails to decode is remembered and not tried again. Images over `huge_pixels` get half-size copies for
    small drawing scales, so a camera photo shown small doesn't resample 100 million pixels every frame."""

    def __init__(self, budget_bytes: int = DEFAULT_BUDGET_BYTES, huge_pixels: int = HUGE_PIXELS):
        self._budget = budget_bytes
        self._huge_pixels = huge_pixels
        self._images: OrderedDict[_Key, skia.Image] = OrderedDict()
        self._failed: set[str] = set()
        self._bytes = 0

    def get(self, data: ImageData, scale: float = 1.0) -> skia.Image | None:
        """The image to draw at `scale` screen pixels per image pixel."""
        original = self._get((data.digest, 0), data)
        if original is None:
            return None
        if original.width() * original.height() <= self._huge_pixels or not 0 < scale < _MIP_BELOW_SCALE:
            return original
        level = min(_MAX_LEVEL, int(math.floor(math.log2(1 / scale))))
        return self._get((data.digest, level), data, original) or original

    def __contains__(self, digest: str) -> bool:
        return (digest, 0) in self._images

    @property
    def decoded_bytes(self) -> int:
        return self._bytes

    def discard(self, digest: str) -> None:
        for key in [key for key in self._images if key[0] == digest]:
            self._drop(key)

    def _get(self, key: _Key, data: ImageData, original: skia.Image | None = None) -> skia.Image | None:
        image = self._images.get(key)
        if image is not None:
            self._images.move_to_end(key)
            return image
        digest, level = key
        if digest in self._failed:
            return None
        if level == 0:
            image = decode(data)
            if image is None:
                self._failed.add(digest)
                return None
        else:
            assert original is not None
            image = _halved(original, level)
        self._images[key] = image
        self._bytes += _cost(image)
        self._evict(keep=key)
        return image

    def _evict(self, keep: _Key) -> None:
        while self._bytes > self._budget and len(self._images) > 1:
            oldest = next(key for key in self._images if key != keep)
            self._drop(oldest)

    def _drop(self, key: _Key) -> None:
        image = self._images.pop(key, None)
        if image is None:
            return
        self._bytes -= _cost(image)
        if key[1] == 0:
            for level_key in [other for other in self._images if other[0] == key[0]]:
                self._drop(level_key)


def _cost(image: skia.Image) -> int:
    return image.width() * image.height() * 4


def _halved(image: skia.Image, level: int) -> skia.Image:
    width, height = max(1, image.width() >> level), max(1, image.height() >> level)
    surface = skia.Surface(width, height)
    surface.getCanvas().drawImageRect(
        image, skia.Rect.MakeWH(image.width(), image.height()), skia.Rect.MakeWH(width, height), _SMOOTH
    )
    return surface.makeImageSnapshot()


def pixel_scale(shape: ImageShape, scale: float) -> float:
    """Screen pixels per image pixel when the document is drawn at `scale`."""
    return scale * visible_box(shape)[2] / max(1, shape.data.width)


def image_sampling(shape: ImageShape, scale: float) -> tuple[bool, int]:
    """What drawing at `scale` decides about an image: whether pixels stay square, and the halving level a huge
    image would use. A recorded picture is valid while this stays the same."""
    per_pixel = pixel_scale(shape, scale)
    level = min(_MAX_LEVEL, int(math.floor(math.log2(1 / per_pixel)))) if 0 < per_pixel < _MIP_BELOW_SCALE else 0
    return per_pixel >= _NEAREST_SCALE, level


def draw_image(
    canvas: skia.Canvas, shape: ImageShape, image: skia.Image | None, opacity: float, zoom: float = 1.0
) -> None:
    """The picture in its viewport as `preserveAspectRatio` says, `opacity` as paint alpha (no layer); the
    placeholder when `image` is None. The caller has applied the shape's transform; `zoom` is the scale the
    canvas matrix lacks (pictures are recorded in document units)."""
    if shape.width <= 0 or shape.height <= 0 or opacity <= 0:
        return
    viewport = skia.Rect.MakeXYWH(shape.x, shape.y, shape.width, shape.height)
    if image is None:
        draw_placeholder(canvas, viewport)
        return
    rect, clipped = fitted_rect(
        shape.data.width, shape.data.height, shape.x, shape.y, shape.width, shape.height, shape.aspect
    )
    if rect[2] <= 0 or rect[3] <= 0:
        return
    paint = skia.Paint(AntiAlias=True)
    paint.setAlphaf(min(1.0, opacity))
    scale = device_scale(canvas) * zoom * rect[2] / image.width()
    sampling = _NEAREST if scale >= _NEAREST_SCALE else _SMOOTH
    destination = skia.Rect.MakeXYWH(*rect)
    if clipped:
        canvas.save()
        canvas.clipRect(viewport)
    canvas.drawImageRect(image, skia.Rect.MakeWH(image.width(), image.height()), destination, sampling, paint)
    if clipped:
        canvas.restore()


def draw_placeholder(canvas: skia.Canvas, box: skia.Rect) -> None:
    """A hairline box with a cross: what stands for a picture that is missing or won't decode."""
    paint = skia.Paint(Color=_PLACEHOLDER_COLOR, Style=skia.Paint.kStroke_Style, StrokeWidth=0, AntiAlias=True)
    canvas.drawRect(box, paint)
    canvas.drawLine(box.left(), box.top(), box.right(), box.bottom(), paint)
    canvas.drawLine(box.right(), box.top(), box.left(), box.bottom(), paint)


def thumbnail(data: ImageData, side: int) -> tuple[bytes, int, int] | None:
    """The picture scaled to fit `side` × `side`, as premultiplied RGBA bytes with its width and height; None
    when it won't decode. Meant for list rows: decodes on every call, so callers keep the result."""
    image = decode(data)
    if image is None:
        return None
    scale = min(1.0, side / max(image.width(), image.height()))
    width, height = max(1, round(image.width() * scale)), max(1, round(image.height() * scale))
    surface = skia.Surface(width, height)
    surface.getCanvas().drawImageRect(
        image, skia.Rect.MakeWH(image.width(), image.height()), skia.Rect.MakeWH(width, height), _SMOOTH
    )
    info = skia.ImageInfo.Make(width, height, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    pixels = bytearray(width * height * 4)
    surface.readPixels(info, pixels, width * 4, 0, 0)
    return bytes(pixels), width, height
