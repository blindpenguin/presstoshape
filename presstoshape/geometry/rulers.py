"""Where ruler ticks go: round steps in the document's unit that stay readable at every zoom."""

import math
from dataclasses import dataclass

from presstoshape.geometry import units
from presstoshape.models.app_state import Unit

# Labelled ticks at least this far apart (screen px), minor ticks at least this far.
_LABEL_SPACING_PX = 60.0
_MINOR_SPACING_PX = 5.0


@dataclass(frozen=True)
class Tick:
    # Screen px from the ruler's start.
    screen: float
    major: bool
    label: str | None


def _round_step(minimum: float) -> float:
    """The smallest 1, 2 or 5 times a power of ten that is at least `minimum`."""
    exponent = math.floor(math.log10(minimum))
    for factor in (1, 2, 5, 10):
        step = factor * 10**exponent
        if step >= minimum:
            return step
    return 10 ** (exponent + 1)


def _label(value: float, step: float) -> str:
    decimals = max(0, -math.floor(math.log10(step))) if step < 1 else 0
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def ruler_ticks(start_doc: float, zoom: float, length_px: float, unit: Unit, dpi: float) -> list[Tick]:
    """Ticks for a ruler whose first pixel shows document coordinate `start_doc` (px) at `zoom` (screen px per
    document px), labelled in `unit`."""
    if zoom <= 0 or length_px <= 0:
        return []
    screen_per_unit = units.to_px(1.0, unit, dpi) * zoom
    step = _round_step(_LABEL_SPACING_PX / screen_per_unit)
    subdivisions = next((count for count in (10, 5, 2) if step / count * screen_per_unit >= _MINOR_SPACING_PX), 1)
    minor = step / subdivisions
    start_unit = units.from_px(start_doc, unit, dpi)
    end_unit = start_unit + length_px / screen_per_unit
    ticks = []
    for index in range(math.floor(start_unit / minor), math.ceil(end_unit / minor) + 1):
        value = index * minor
        screen = (value - start_unit) * screen_per_unit
        major = index % subdivisions == 0
        ticks.append(Tick(screen, major, _label(value, step) if major else None))
    return ticks
