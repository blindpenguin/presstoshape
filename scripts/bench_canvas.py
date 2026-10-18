"""Dev-only: canvas frame-time benchmark on a generated large document.

Repaints the real canvas while panning, zooming, and moving/scaling/rotating a selection, and reports average and
95th-percentile frame time. Gesture frames include the gesture's own per-move work (e.g. rebuilding scaled
shapes). GL frames wait for the GPU to finish, so times include GPU work. `hover` times the cursor query alone.

Usage: uv run python scripts/bench_canvas.py [--shapes N] [--frames N]
       PRESSTOSHAPE_RENDERER=cpu uv run python scripts/bench_canvas.py   # CPU raster path
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

from presstoshape.app import _set_surface_format  # noqa: E402
from presstoshape.editing import queries  # noqa: E402
from presstoshape.editing.operations import selection, view  # noqa: E402
from presstoshape.editing.session import Session  # noqa: E402
from presstoshape.models.app_state import AppState, Document, Layer  # noqa: E402
from presstoshape.models.shapes import (  # noqa: E402
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.handles import Handle  # noqa: E402
from presstoshape.tools.base import Mods  # noqa: E402
from presstoshape.tools.select import _Mode  # noqa: E402
from presstoshape.views import theme  # noqa: E402
from presstoshape.views.main_window import MainWindow  # noqa: E402
from presstoshape.views.skia_surface import SkiaGLWidget  # noqa: E402


def _document(count: int) -> Document:
    rng = random.Random(1)
    side = 4000.0
    shapes = []
    for i in range(count):
        x, y = rng.uniform(0, side), rng.uniform(0, side)
        style = Style(fill=f"#{rng.randrange(0x1000000):06x}", stroke="#18181b", stroke_width=rng.choice((0, 1, 2)))
        match i % 10:
            case 0:
                shapes.append(TextShape(i, x, y, "shape", rng.uniform(8, 32), style))
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


def _measure(viewport, step, frames: int, include_step: bool = False) -> list[float]:
    times = []
    for i in range(frames):
        if not include_step:
            step(i)
        start = time.perf_counter()
        if include_step:
            step(i)
        _frame(viewport)
        times.append((time.perf_counter() - start) * 1000)
    return times


def _start_gesture(select, mode: _Mode, handle: Handle | None = None) -> tuple[float, float]:
    """Puts the select gesture mid-gesture on the current selection without hit-testing a start point."""
    frame = select.frame()
    select._mode, select._handle, select._frame0 = mode, handle, frame
    select._moving = queries.selected_shapes(select._context.state)
    select._start = frame.point(*handle.fraction) if handle is not None else (0.0, 0.0)
    return select._start


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
    session = Session(state)
    window = MainWindow(session)
    window.resize(1600, 1000)
    window.show()
    QTest.qWaitForWindowExposed(window)
    canvas = window.canvas
    view.set_zoom(session, 25)
    canvas.center_artboard()
    viewport = canvas.viewport()
    if isinstance(viewport, SkiaGLWidget):
        _sync_gpu(viewport)
    print(f"{type(viewport).__name__}, {args.shapes} shapes, {viewport.width()}x{viewport.height()} px")
    _frame(viewport)

    _report("pan", _measure(viewport, lambda i: canvas._scroll_by(7 if i % 40 < 20 else -7, 3), args.frames))
    zooms = [25 * 1.02**k for k in range(30)]
    _report("zoom", _measure(viewport, lambda i: view.set_zoom(session, zooms[i % 30]), args.frames))

    view.set_zoom(session, 25)
    shapes = state.document.layers[0].shapes
    selection.set_selection(session, {shape.id for shape in shapes[:500]})
    select = canvas._toolbox.active
    none = Mods()

    _start_gesture(select, _Mode.MOVE)
    _report("drag", _measure(viewport, lambda i: select.move((float(i), float(i)), none), args.frames, True))
    select.cancel()

    x0, y0 = _start_gesture(select, _Mode.SCALE, Handle.SE)
    _report("scale", _measure(viewport, lambda i: select.move((x0 + i, y0 + i / 2), none), args.frames, True))
    select.cancel()

    x0, y0 = _start_gesture(select, _Mode.ROTATE, Handle.ROTATE_NE)
    _report("rotate", _measure(viewport, lambda i: select.move((x0 - 3 * i, y0 + 5 * i), none), args.frames, True))
    select.cancel()

    rng = random.Random(2)
    side = state.document.width
    hover_times = []
    for _ in range(args.frames):
        point = (rng.uniform(0, side), rng.uniform(0, side))
        start = time.perf_counter()
        canvas._toolbox.active.hover(point)
        hover_times.append((time.perf_counter() - start) * 1000)
    _report("hover", hover_times)

    window.close_without_prompt()


if __name__ == "__main__":
    main()
