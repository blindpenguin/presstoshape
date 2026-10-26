"""Colour picking: swatches (the document's and those of the stored palettes) and the colour panel's view state."""

from dataclasses import dataclass, field
from typing import Literal

from presstoshape.models.shapes import Style

PaintSlot = Literal["fill", "stroke"]
NumberMode = Literal["hsv", "rgb"]
RECENT_LIMIT = 16


@dataclass(frozen=True)
class Swatch:
    # Document swatches: from Document.next_id, shared with shapes, so paints can refer to them later.
    # Swatches of stored palettes: numbered within their palette.
    id: int
    name: str
    # "#rrggbb"
    color: str
    opacity: float = 1.0


@dataclass(frozen=True)
class Palette:
    """A stored palette. Ids are numbered per run; on disk a palette is its own file."""

    id: int
    name: str
    swatches: tuple[Swatch, ...] = ()


@dataclass
class ColourState:
    """App-level colour state: not part of the document or undo."""

    active: PaintSlot = "fill"
    # What the panel edits when nothing is selected and no drawing tool is active; the eyedropper fills it.
    current: Style = field(default_factory=Style)
    # Newest first, at most RECENT_LIMIT; kept in app settings.
    recent: tuple[str, ...] = ()
    # The stored palettes (the library), one file each in the app's data folder, in the user's order.
    palettes: tuple[Palette, ...] = ()
    # The palette the Library tab shows and adds to; None only when there are no palettes.
    current_palette: int | None = None
    numbers: NumberMode = "hsv"
