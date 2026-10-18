"""Inputs to the renderer that aren't document content: canvas colors and transient gesture feedback."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from veccy.models.shapes import Segment, Shape, Style

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class CanvasColors:
    """Hex colors; views fill these from their theme since render can't import views."""

    pasteboard: str
    artboard: str
    artboard_border: str
    preview: str
    selection: str


@dataclass(frozen=True)
class Overlay:
    selection: frozenset[int] = frozenset()
    # Doc coordinates x, y, w, h.
    rubber_band: Rect | None = None
    preview: tuple[tuple[Segment, ...], Style] | None = None
    # Shapes drawn in place of the document's while a drag is live.
    overrides: Mapping[int, Shape] = field(default_factory=dict)
