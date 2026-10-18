"""Dev-only: canvas frame-time benchmark on a generated large document.

Repaints the real canvas while panning, zooming and dragging a selection, and reports average and 95th-percentile
frame time. GL frames wait for the GPU to finish, so times include GPU work.

Usage: uv run python scripts/bench_canvas.py [--shapes N] [--frames N]
       VECCY_RENDERER=cpu uv run python scripts/bench_canvas.py   # CPU raster path
"""

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import skia  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from veccy.app import _set_surface_format  # noqa: E402
from veccy.controllers.app_controller import AppController  # noqa: E402
from veccy.models.app_state import AppState, Document, Layer  # noqa: E402
from veccy.models.shapes import EllipseShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape  # noqa: E402
from veccy.views import theme  # noqa: E402
from veccy.views.main_window import MainWindow  # noqa: E402
from veccy.views.skia_surface import SkiaGLWidget  # noqa: E402


def _document(count: int) -> Document:
    rng = random.Random(1)
    side = 4000.0
    shapes = []
    for i in range(count):
        x, y = rng.uniform(0, side), rng.uniform(0, side)
        style = Style(fill=f"#{rng.randrange(0x1000000):06x}", stroke="#18181b", stroke_width=rng.choice((0, 1, 2)))
        match i % 10:
            case 0:
                shapes.append(TextShape(i, x, y, "veccy", rng.uniform(8, 32), style))
            case 1 | 2:
                pts = [MoveTo(x, y)] + [LineTo(x + rng.uniform(-60, 60), y + rng.uniform(-60, 60)) for _ in range(6)]
                shapes.append(PathShape(i, tuple(pts), Style(fill=None, stroke=style.fill, stroke_width=2)))
            case 3 | 4 | 5:
                shapes.append(EllipseShape(i, x, y, rng.uniform(5, 40), rng.uniform(5, 40), style))
            case _:
                shapes.append(RectShape(i, x, y, rng.uniform(5, 80), rng.uniform(5, 80), style))
    return Document(side, side, [Layer("Bench", True, shapes)], next_id=count + 1)


def _sync_gpu(widget: SkiaGLWidget) -> None:
    original = widget.paintGL

    def paint_and_wait() -> None:
        original()
        if widget._context is not None:
            widget._context.flushAndSubmit(skia.GrSyncCpu.kYes)

    widget.paintGL = paint_and_wait


def _frame(viewport) -> None:
    # QOpenGLWidget.repaint() only schedules paintGL, so GL frames are rendered directly.
    if isinstance(viewport, SkiaGLWidget):
        viewport.makeCurrent()
        viewport.paintGL()
        viewport.doneCurrent()
    else:
        viewport.repaint()


def _measure(viewport, step, frames: int) -> list[float]:
    times = []
    for i in range(frames):
        step(i)
        start = time.perf_counter()
        _frame(viewport)
        times.append((time.perf_counter() - start) * 1000)
    return times


def _report(name: str, times: list[float]) -> None:
    p95 = statistics.quantiles(times, n=20)[-1]
    print(f"{name:<6} avg {statistics.mean(times):6.2f} ms   p95 {p95:6.2f} ms")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shapes", type=int, default=10_000)
    parser.add_argument("--frames", type=int, default=120)
    args = parser.parse_args()

    _set_surface_format()
    app = QApplication(sys.argv)
    theme.apply(app)
    state = AppState(document=_document(args.shapes))
    controller = AppController(state)
    window = MainWindow(state, controller)
    window.resize(1600, 1000)
    window.show()
    QTest.qWaitForWindowExposed(window)
    canvas = window.canvas
    controller.set_zoom(25)
    canvas.center_artboard()
    viewport = canvas.viewport()
    if isinstance(viewport, SkiaGLWidget):
        _sync_gpu(viewport)
    print(f"{type(viewport).__name__}, {args.shapes} shapes, {viewport.width()}x{viewport.height()} px")
    _frame(viewport)

    _report("pan", _measure(viewport, lambda i: canvas._scroll_by(7 if i % 40 < 20 else -7, 3), args.frames))
    zooms = [25 * 1.02**k for k in range(30)]
    _report("zoom", _measure(viewport, lambda i: controller.set_zoom(zooms[i % 30]), args.frames))

    controller.set_zoom(25)
    shapes = state.document.layers[0].shapes
    controller.set_selection({s.id for s in shapes[:500]})
    # Puts the select gesture mid-drag of 500 shapes without hit-testing a start point.
    gestures = canvas._gestures
    gestures._moving = controller.selected_shapes()
    gestures._drag_start = (0.0, 0.0)
    _report("drag", _measure(viewport, lambda i: gestures.move((float(i), float(i)), False), args.frames))
    gestures.cancel()

    window.close_without_prompt()


if __name__ == "__main__":
    main()
