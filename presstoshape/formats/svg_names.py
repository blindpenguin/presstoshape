"""SVG namespaces and the qualified names PressToShape's reader and writer share."""

import xml.etree.ElementTree as ET

from presstoshape.formats.svg_page import PRESSTOSHAPE_NS

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
# Composite definitions live in PRESSTOSHAPE_NS, inside the result path's <metadata>: viewers don't render it
# and Inkscape keeps it.
ET.register_namespace("inkscape", INKSCAPE_NS)
ET.register_namespace("presstoshape", PRESSTOSHAPE_NS)
COMPOSITE = f"{{{PRESSTOSHAPE_NS}}}composite"
MODE = f"{{{PRESSTOSHAPE_NS}}}mode"
PART_MODES = ("add", "subtract", "intersect", "exclude")
GROUPMODE = f"{{{INKSCAPE_NS}}}groupmode"
LABEL = f"{{{INKSCAPE_NS}}}label"
XLINK_HREF = f"{{{XLINK_NS}}}href"
SVG_PREFIX = f"{{{SVG_NS}}}"


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"
