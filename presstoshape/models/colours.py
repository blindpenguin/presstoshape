"""Colour picking: swatches (document palette and the personal library) and the colour panel's view state."""

from dataclasses import dataclass, field
from typing import Literal

from presstoshape.models.shapes import Style

PaintSlot = Literal["fill", "stroke"]
NumberMode = Literal["hsv", "rgb"]
RECENT_LIMIT = 16


@dataclass(frozen=True)
class Swatch:
    # Document swatches: from Document.next_id, shared with shapes, so paints can refer to them later.
    # Library swatches: numbered within the library.
    id: int
    name: str
    # "#rrggbb"
    color: str
    opacity: float = 1.0


@dataclass
class ColourState:
    """App-level colour state: not part of the document or undo."""

    active: PaintSlot = "fill"
    # What the panel edits when nothing is selected and no drawing tool is active; the eyedropper fills it.
    current: Style = field(default_factory=Style)
    # Newest first, at most RECENT_LIMIT; kept in app settings.
    recent: tuple[str, ...] = ()
    # The personal swatch library, kept in the app's data folder.
    library: tuple[Swatch, ...] = ()
    numbers: NumberMode = "hsv"
