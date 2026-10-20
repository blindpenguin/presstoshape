"""Inputs to the renderer that aren't document content: canvas colors and transient gesture feedback."""

from dataclasses import dataclass

from presstoshape.geometry.boxes import Rect
from presstoshape.geometry.snapping import SnapHit
from presstoshape.models.layout import Guide
from presstoshape.models.shapes import IDENTITY_TRANSFORM, Segment, Shape, Style, Transform
from presstoshape.render.handles import Frame


@dataclass(frozen=True)
class CanvasColors:
    """Hex colors; views fill these from their theme since render can't import views."""

    pasteboard: str
    artboard: str
    artboard_border: str
    preview: str
    selection: str
    guide: str = "#06b6d4"
    grid: str = "#64748b"
    snap: str = "#f97316"


@dataclass(frozen=True)
class NodeOverlay:
    """One path being node-edited: its (live) segments, selected node indices and the controls to show."""

    segments: tuple[Segment, ...]
    selected: frozenset[int] = frozenset()
    controls: frozenset[tuple[int, int]] = frozenset()


@dataclass(frozen=True)
class Overlay:
    selection: frozenset[int] = frozenset()
    # Doc coordinates x, y, w, h.
    rubber_band: Rect | None = None
    preview: tuple[tuple[Segment, ...], Style] | None = None
    # Shapes being dragged, drawn through `matrix` (doc space) until the gesture commits, or replaced by `live`
    # (exact previews, e.g. scaling, where a matrix would also scale strokes).
    moving: frozenset[int] = frozenset()
    matrix: Transform = IDENTITY_TRANSFORM
    live: tuple[Shape, ...] = ()
    # Shapes drawn a second time through `matrix`, on top, while the originals stay put (Alt+drag duplicate).
    copies: tuple[Shape, ...] = ()
    # Selection frame with handles, already following the live gesture.
    frame: Frame | None = None
    nodes: tuple[NodeOverlay, ...] = ()
    # What the running gesture snapped to, for feedback lines and labels.
    snap: tuple[SnapHit, ...] = ()
    # A guide being dragged: drawn here instead of where the document has it (same id), or a new one (id -1).
    guide_preview: Guide | None = None
