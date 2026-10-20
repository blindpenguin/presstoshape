"""Guides and the grid in SVG, in the `sodipodi:namedview` element Inkscape reads and writes, so they travel
with the file both ways.

Format facts this relies on: a `sodipodi:guide` has `position="x,y"` in user units relative to the viewBox, with
y measured up from the viewBox's bottom edge, and `orientation="nx,ny"`, the guide's normal (so a vertical guide
has a horizontal normal). An `inkscape:grid` has `spacingx`/`spacingy` in user units (older files add a unit
suffix), `empspacing` for the major line interval, and an origin. PressToShape writes and reads these on its own
terms; only axis-aligned guides and rectangular grids are supported.
"""

import math
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable

from presstoshape.formats.svg_names import INKSCAPE_NS, SODIPODI_NS
from presstoshape.formats.svg_notes import Note, NoteCollector
from presstoshape.formats.svg_page import Page
from presstoshape.formats.svg_page import number_text as _num
from presstoshape.geometry import units
from presstoshape.models.app_state import Document
from presstoshape.models.layout import GridSettings, Guide

_NAMEDVIEW = f"{{{SODIPODI_NS}}}namedview"
_GUIDE = f"{{{SODIPODI_NS}}}guide"
_GRID = f"{{{INKSCAPE_NS}}}grid"
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_LENGTH = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-zA-Z]*)\s*$")
# A normal component this small counts as zero: the guide is axis-aligned.
_AXIS_EPSILON = 1e-6


def namedview_element(document: Document) -> ET.Element:
    """Guides and the document's own grid, in a namedview for the root. Our files' user units are document px
    with the viewBox at the origin, so positions only need the y flip."""
    namedview = ET.Element(_NAMEDVIEW, {"showguides": "true", f"{{{INKSCAPE_NS}}}document-units": document.unit})
    for guide in document.guides:
        if guide.orientation == "horizontal":
            attributes = {"position": f"0,{_num(document.height - guide.position)}", "orientation": "0,-1"}
        else:
            attributes = {"position": f"{_num(guide.position)},0", "orientation": "1,0"}
        ET.SubElement(namedview, _GUIDE, {"id": f"guide{guide.id}", **attributes})
    if document.grid is not None:
        spacing = _num(document.grid.spacing, 6)
        ET.SubElement(
            namedview,
            _GRID,
            {
                "id": "grid1",
                "type": "xygrid",
                "units": document.unit,
                "originx": "0",
                "originy": "0",
                "spacingx": spacing,
                "spacingy": spacing,
                "empspacing": str(document.grid.major_every),
                "enabled": "true",
                "visible": "true",
            },
        )
    return namedview


def read_namedview(
    root: ET.Element, page: Page, new_id: Callable[[], int], notes: NoteCollector
) -> tuple[tuple[Guide, ...], GridSettings | None]:
    namedview = root.find(_NAMEDVIEW)
    if namedview is None:
        return (), None
    view_height = page.height / page.scale
    guides = []
    for element in namedview.iter(_GUIDE):
        guide = _guide(element, view_height, page.scale, new_id)
        if guide is None:
            notes.add(Note.ANGLED_GUIDE)
        else:
            guides.append(guide)
    grid = None
    element = namedview.find(_GRID)
    if element is not None and element.get("type", "xygrid") in ("xygrid", "rectangular"):
        grid = _grid(element, page)
        if grid is None:
            notes.add(Note.BROKEN_GRID)
    return tuple(guides), grid


def _numbers(text: str | None) -> list[float]:
    return [float(value) for value in _NUMBER.findall(text or "")]


def _guide(element: ET.Element, view_height: float, scale: float, new_id: Callable[[], int]) -> Guide | None:
    """An axis-aligned guide in document px, or None for angled or unreadable ones."""
    position, normal = _numbers(element.get("position")), _numbers(element.get("orientation"))
    if len(position) != 2 or len(normal) != 2 or not all(math.isfinite(value) for value in position + normal):
        return None
    normal_x, normal_y = abs(normal[0]), abs(normal[1])
    if normal_x > _AXIS_EPSILON and normal_y > _AXIS_EPSILON:
        return None
    if normal_x > normal_y:
        return Guide(new_id(), "vertical", position[0] * scale)
    return Guide(new_id(), "horizontal", (view_height - position[1]) * scale)


def _grid(element: ET.Element, page: Page) -> GridSettings | None:
    spacing = _spacing(element.get("spacingx"), page) or _spacing(element.get("spacingy"), page)
    if spacing is None:
        return None
    try:
        major_every = int(element.get("empspacing", "5"))
    except ValueError:
        return None
    return GridSettings(spacing, major_every) if major_every >= 1 else None


def _spacing(text: str | None, page: Page) -> float | None:
    """Grid spacing in document px: user units, or a length with a physical unit (older files)."""
    match = _LENGTH.match(text or "")
    if match is None:
        return None
    value, unit = float(match.group(1)), match.group(2).lower()
    if not math.isfinite(value) or value <= 0:
        return None
    if unit in ("", "px"):
        return value * page.scale
    if unit in units.PER_INCH:
        return value / units.PER_INCH[unit] * page.dpi
    return None
