"""Document swatches in SVG, the way Inkscape keeps them: a one-stop `<linearGradient>` in `<defs>` marked
`inkscape:swatch="solid"` (Inkscape 0.92: `osb:paint="solid"`). Nothing references them, so they draw nothing."""

import xml.etree.ElementTree as ET
from collections.abc import Callable

from presstoshape.formats.svg_gradients import StopStyle, resolve_gradient
from presstoshape.formats.svg_lengths import Viewport
from presstoshape.formats.svg_names import LABEL, OSB_PAINT, SWATCH, q
from presstoshape.formats.svg_notes import Note, NoteCollector
from presstoshape.formats.svg_page import number_text
from presstoshape.formats.svg_paint import PaintDefs
from presstoshape.models.colours import Swatch
from presstoshape.models.shapes import flat_color


def add_swatches(swatches: tuple[Swatch, ...], defs: PaintDefs) -> None:
    for swatch in swatches:
        attrs = {"id": defs.new_id("swatch"), SWATCH: "solid"}
        if swatch.name:
            attrs[LABEL] = swatch.name
        element = ET.Element(q("linearGradient"), attrs)
        ET.SubElement(
            element,
            q("stop"),
            {"offset": "0", "style": f"stop-color:{swatch.color};stop-opacity:{number_text(swatch.opacity, 6)}"},
        )
        defs.add_definition(element)


def read_swatches(
    root: ET.Element,
    ids: dict[str, ET.Element],
    stop_style: StopStyle,
    new_id: Callable[[], int],
    notes: NoteCollector,
) -> tuple[Swatch, ...]:
    """The solid swatches of the file in document order; gradient swatches are noted, not kept."""
    swatches = []
    for element in root.iter(q("linearGradient")):
        kind = element.get(SWATCH) or element.get(OSB_PAINT)
        if kind is None:
            continue
        if kind != "solid":
            notes.add(Note.SWATCH_GRADIENT)
            continue
        resolved = resolve_gradient(element, ids, stop_style, Viewport(1.0, 1.0))
        color = flat_color(resolved.paint) if resolved is not None else None
        if color is None:
            continue
        if isinstance(resolved.paint, str):
            opacity = resolved.opacity
        else:
            opacity = resolved.paint.stops[0].opacity
        name = element.get(LABEL) or element.get("id") or ""
        swatches.append(Swatch(new_id(), name, color.lower(), min(1.0, max(0.0, opacity))))
    return tuple(swatches)
