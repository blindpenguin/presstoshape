"""Precision aids: guides and the grid (document data, undoable), and how the canvas shows them and snaps (view
state, not undoable)."""

from dataclasses import dataclass
from typing import Literal

GuideOrientation = Literal["horizontal", "vertical"]
AlignReference = Literal["selection", "artboard"]


@dataclass(frozen=True)
class Guide:
    # From Document.next_id, shared with shapes.
    id: int
    orientation: GuideOrientation
    # Document px: y of a horizontal guide, x of a vertical one.
    position: float


@dataclass(frozen=True)
class GridSettings:
    # Document px between minor lines.
    spacing: float
    # Every N-th line is a major line, drawn stronger.
    major_every: int = 5


@dataclass(frozen=True)
class SnapSettings:
    enabled: bool = True
    grid: bool = False
    guides: bool = True
    artboard: bool = True
    objects: bool = True
    nodes: bool = True
    # Screen px, so snapping feels the same at every zoom.
    distance_px: float = 8.0


@dataclass(frozen=True)
class ViewOptions:
    show_rulers: bool = True
    show_grid: bool = False
    show_guides: bool = True
    lock_guides: bool = False
