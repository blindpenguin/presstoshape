"""Lengths in document pixels (1/dpi inch) shown and entered in other units. Only views convert; operations,
geometry and rendering work in document pixels."""

from presstoshape.models.app_state import Document, Unit
from presstoshape.models.layout import GridSettings

UNITS: tuple[Unit, ...] = ("px", "mm", "cm", "in", "pt")
# Physical units per inch; px depends on the document's DPI.
PER_INCH: dict[Unit, float] = {"mm": 25.4, "cm": 2.54, "in": 1.0, "pt": 72.0}
# One arrow-key nudge per unit: a round step in the unit people measure in (about half a millimetre for the
# physical ones). Shift nudges ten times as far.
NUDGE_STEP: dict[Unit, float] = {"px": 1.0, "mm": 0.5, "cm": 0.05, "in": 0.02, "pt": 1.0}
# Default grid per unit: (spacing in the unit, major line every N), round numbers people lay out with.
GRID_DEFAULTS: dict[Unit, tuple[float, int]] = {
    "px": (10.0, 10),
    "mm": (5.0, 2),
    "cm": (0.5, 2),
    "in": (0.25, 4),
    "pt": (12.0, 6),
}
# Decimals worth showing per unit.
DECIMALS: dict[Unit, int] = {"px": 2, "mm": 2, "cm": 3, "in": 3, "pt": 2}
MIN_DPI = 1.0
MAX_DPI = 9600.0
# Largest document side in document pixels; far beyond any real page, small enough for float precision.
MAX_DOCUMENT_PX = 100_000.0


def is_physical(unit: Unit) -> bool:
    return unit != "px"


def to_px(value: float, unit: Unit, dpi: float) -> float:
    return value if unit == "px" else value / PER_INCH[unit] * dpi


def from_px(px: float, unit: Unit, dpi: float) -> float:
    return px if unit == "px" else px / dpi * PER_INCH[unit]


def convert(value: float, source: Unit, target: Unit, dpi: float) -> float:
    return from_px(to_px(value, source, dpi), target, dpi)


def nudge_px(unit: Unit, dpi: float) -> float:
    return to_px(NUDGE_STEP[unit], unit, dpi)


def default_grid(unit: Unit, dpi: float) -> GridSettings:
    spacing, major_every = GRID_DEFAULTS[unit]
    return GridSettings(to_px(spacing, unit, dpi), major_every)


def grid_of(document: Document) -> GridSettings:
    """The document's grid, or the default for its unit when it has none of its own."""
    return document.grid if document.grid is not None else default_grid(document.unit, document.dpi)
