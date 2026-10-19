"""Widgets that hand a skia.Canvas to a paint callback: GPU via OpenGL, or CPU raster as fallback."""

import os
from collections.abc import Callable

import skia
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

# (canvas, width_px, height_px, device_pixel_ratio)
PaintCallback = Callable[[skia.Canvas, int, int, float], None]

_GL_RGBA8 = 0x8058


def _device_size(widget: QWidget) -> tuple[int, int, float]:
    dpr = widget.devicePixelRatioF()
    return round(widget.width() * dpr), round(widget.height() * dpr), dpr


class SkiaGLWidget(QOpenGLWidget):
    gl_failed = Signal()

    def __init__(self, paint: PaintCallback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paint = paint
        self._context: skia.GrDirectContext | None = None
        self._surface: skia.Surface | None = None
        self._surface_key: tuple[int, int, int] | None = None

    def initializeGL(self) -> None:
        self._surface = None
        context = skia.GrDirectContext.MakeGL()
        if context is None:
            # Skia's native interface loads GL through GLX; Qt on Wayland (and EGL setups on X11) runs on EGL.
            interface = skia.GrGLInterface.MakeEGL()
            context = skia.GrDirectContext.MakeGL(interface) if interface is not None else None
        self._context = context
        if context is None:
            self.gl_failed.emit()
            return
        # Skia must stop using the GL context before it dies. This also fires from the widget's C++ destructor,
        # when `self` is already gone, so it only abandons (no GL calls); release() is the full cleanup.
        self.context().aboutToBeDestroyed.connect(lambda: context.abandoned() or context.abandonContext())

    def paintGL(self) -> None:
        width, height, dpr = _device_size(self)
        if self._context is None or width <= 0 or height <= 0:
            return
        # Qt touched GL state since our last frame; Skia must not trust its cached view of it.
        self._context.resetContext()
        key = (width, height, self.defaultFramebufferObject())
        if self._surface is None or key != self._surface_key:
            fmt = self.format()
            target = skia.GrBackendRenderTarget(
                width,
                height,
                max(fmt.samples(), 0),
                fmt.stencilBufferSize(),
                skia.GrGLFramebufferInfo(key[2], _GL_RGBA8),
            )
            self._surface = skia.Surface.MakeFromBackendRenderTarget(
                self._context,
                target,
                skia.kBottomLeft_GrSurfaceOrigin,
                skia.kRGBA_8888_ColorType,
                skia.ColorSpace.MakeSRGB(),
            )
            self._surface_key = key
        if self._surface is None:
            return
        canvas = self._surface.getCanvas()
        canvas.save()
        self._paint(canvas, width, height, dpr)
        canvas.restore()
        self._surface.flushAndSubmit()

    def release(self) -> None:
        if self._context is None:
            return
        self.makeCurrent()
        self._surface = None
        self._context.releaseResourcesAndAbandonContext()
        self._context = None
        self.doneCurrent()


class SkiaRasterWidget(QWidget):
    def __init__(self, paint: PaintCallback, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paint = paint
        self._surface: skia.Surface | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def paintEvent(self, event) -> None:
        width, height, dpr = _device_size(self)
        if width <= 0 or height <= 0:
            return
        if self._surface is None or (self._surface.width(), self._surface.height()) != (width, height):
            info = skia.ImageInfo.Make(width, height, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
            self._surface = skia.Surface.MakeRaster(info)
        canvas = self._surface.getCanvas()
        canvas.save()
        self._paint(canvas, width, height, dpr)
        canvas.restore()
        pixels = self._surface.makeImageSnapshot().tobytes()
        image = QImage(pixels, width, height, width * 4, QImage.Format.Format_RGBA8888_Premultiplied)
        image.setDevicePixelRatio(dpr)
        QPainter(self).drawImage(0, 0, image)

    def release(self) -> None:
        self._surface = None


RENDERER_VARIABLE = "PRESSTOSHAPE_RENDERER"


def renderer_override() -> str | None:
    """"gl" or "cpu" when the environment variable forces one; it wins over the setting."""
    choice = os.environ.get(RENDERER_VARIABLE, "").lower()
    return choice if choice in ("cpu", "gl") else None


def use_gpu(preference: str = "auto") -> bool:
    """`preference` is the renderer setting: "auto", "gl" or "cpu"."""
    choice = renderer_override() or preference
    if choice in ("cpu", "gl"):
        return choice == "gl"
    return QGuiApplication.platformName() != "offscreen"


def create_surface(
    paint: PaintCallback, preference: str = "auto", parent: QWidget | None = None
) -> SkiaGLWidget | SkiaRasterWidget:
    return SkiaGLWidget(paint, parent) if use_gpu(preference) else SkiaRasterWidget(paint, parent)
