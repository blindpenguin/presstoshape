"""Pencil tool: drag to draw freehand; on release the stroke becomes a smooth path (geometry.fitting)."""

from presstoshape.editing.operations import shapes
from presstoshape.geometry.boxes import Point
from presstoshape.geometry.fitting import StrokeSample, fit_stroke
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import LineTo, MoveTo, Segment
from presstoshape.render.overlay import Overlay
from presstoshape.tools.base import BaseTool, Mods, ToolContext

# Samples closer than this (screen px) add nothing to the stroke but work for the preview and the fitting.
_SAMPLE_SPACING_PX = 0.5


class PencilTool(BaseTool):
    def __init__(self, context: ToolContext) -> None:
        super().__init__(context)
        self._samples: list[StrokeSample] = []
        # The raw stroke as drawn so far, grown point by point (no refit while drawing).
        self._preview: tuple[Segment, ...] = ()

    @property
    def active(self) -> bool:
        return bool(self._samples)

    @property
    def overlay(self) -> Overlay:
        state = self._context.state
        preview = (self._preview, state.tool_styles[Tool.PENCIL]) if len(self._preview) > 1 else None
        return Overlay(frozenset(state.selection), preview=preview)

    def press(self, point: Point, mods: Mods) -> None:
        self._samples = [StrokeSample(*point)]
        self._preview = (MoveTo(*point),)

    def move(self, point: Point, mods: Mods) -> None:
        if not self._samples:
            return
        last = self._samples[-1]
        spacing = _SAMPLE_SPACING_PX * self._context.pixel_size
        if abs(point[0] - last.x) + abs(point[1] - last.y) < spacing:
            return
        self._samples.append(StrokeSample(*point))
        self._preview += (LineTo(*point),)
        self._context.repaint()

    def release(self, point: Point, mods: Mods) -> None:
        if not self._samples:
            return
        self.move(point, mods)
        state = self._context.state
        fitted = fit_stroke(self._samples, state.pencil_smoothing, self._context.pixel_size)
        self.cancel()
        if fitted is not None:
            segments, _closed = fitted
            shapes.add_drawn_path(self._context.session, segments, Tool.PENCIL)
        self._context.repaint()

    def cancel(self) -> None:
        self._samples = []
        self._preview = ()
