"""The page of an SVG file: its physical size and the matching document size, unit and DPI.

PressToShape writes `width="210mm"` with the viewBox in document pixels, plus its own unit and DPI attributes for
an exact round trip. Reading other files, a physical width and the viewBox give the density of user units per
inch. Dense enough (≥ 72 per inch) keeps the coordinates as document pixels at that DPI; coarser (Inkscape's
mm-based files have 25.4) scales the content to 96 DPI, so coordinates and stroke widths stay usable.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from presstoshape.geometry import units
from presstoshape.models.app_state import Document, Unit

PRESSTOSHAPE_NS = "https://github.com/blindpenguin/presstoshape/ns/svg/1"
UNIT_ATTRIBUTE = f"{{{PRESSTOSHAPE_NS}}}unit"
DPI_ATTRIBUTE = f"{{{PRESSTOSHAPE_NS}}}dpi"
_CSS_DPI = 96.0
_MIN_DENSITY = 72.0
_LENGTH = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]*)\s*$")
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
# SVG length units PressToShape can use as a document unit; pc (pica) becomes pt.
_FILE_UNITS: dict[str, tuple[Unit, float]] = {
    "mm": ("mm", 1.0),
    "cm": ("cm", 1.0),
    "in": ("in", 1.0),
    "pt": ("pt", 1.0),
    "pc": ("pt", 12.0),
}


def number_text(value: float, digits: int = 3) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


@dataclass(frozen=True)
class Page:
    # Document size in document pixels.
    width: float
    height: float
    # viewBox origin, moved to 0,0.
    origin: tuple[float, float]
    # Factor from the file's user units to document pixels.
    scale: float
    unit: Unit
    dpi: float


def page_attributes(document: Document) -> dict[str, str]:
    """Root attributes for a document: physical size (plain px for px documents), viewBox, unit and DPI."""
    width, height = number_text(document.width), number_text(document.height)
    attributes = {"viewBox": f"0 0 {width} {height}"}
    if units.is_physical(document.unit):
        for name, size in (("width", document.width), ("height", document.height)):
            attributes[name] = number_text(units.from_px(size, document.unit, document.dpi), 4) + document.unit
    else:
        attributes.update(width=width, height=height)
    attributes[UNIT_ATTRIBUTE] = document.unit
    attributes[DPI_ATTRIBUTE] = number_text(document.dpi)
    return attributes


def _length(value: str | None) -> tuple[float, str] | None:
    match = _LENGTH.match(value or "")
    return (float(match.group(1)), match.group(2).lower()) if match else None


def _inches(length: tuple[float, str]) -> tuple[Unit, float] | None:
    """(document unit, size in inches) for a physical length, else None."""
    value, unit = length
    if unit not in _FILE_UNITS:
        return None
    document_unit, factor = _FILE_UNITS[unit]
    return document_unit, value * factor / units.PER_INCH[document_unit]


def _own_unit_and_dpi(root: ET.Element) -> tuple[Unit, float] | None:
    unit = root.get(UNIT_ATTRIBUTE)
    try:
        dpi = float(root.get(DPI_ATTRIBUTE, ""))
    except ValueError:
        return None
    if unit in units.UNITS and units.MIN_DPI <= dpi <= units.MAX_DPI:
        return unit, dpi
    return None


def _css_px(length: tuple[float, str] | None, default: float) -> float:
    """A width/height without viewBox in CSS px (96 per inch); unknown units count as px."""
    if length is None or length[0] <= 0:
        return default
    physical = _inches(length)
    return physical[1] * _CSS_DPI if physical is not None else length[0]


def read_page(root: ET.Element) -> Page:
    view_box = [float(value) for value in _NUMBER.findall(root.get("viewBox", ""))]
    width, height = _length(root.get("width")), _length(root.get("height"))
    if len(view_box) != 4 or view_box[2] <= 0 or view_box[3] <= 0:
        # Without a viewBox, user units are CSS px.
        physical = _inches(width) if width is not None else None
        unit = physical[0] if physical is not None else "px"
        return Page(_css_px(width, 600.0), _css_px(height, 400.0), (0.0, 0.0), 1.0, unit, _CSS_DPI)
    origin, box_width, box_height = (view_box[0], view_box[1]), view_box[2], view_box[3]
    own = _own_unit_and_dpi(root)
    if own is not None:
        return Page(box_width, box_height, origin, 1.0, *own)
    physical = _inches(width) if width is not None else None
    if physical is None or physical[1] <= 0:
        return Page(box_width, box_height, origin, 1.0, "px", _CSS_DPI)
    unit, inches = physical
    density = box_width / inches
    if _MIN_DENSITY <= density <= units.MAX_DPI:
        return Page(box_width, box_height, origin, 1.0, unit, density)
    scale = _CSS_DPI / density
    return Page(box_width * scale, box_height * scale, origin, scale, unit, _CSS_DPI)
