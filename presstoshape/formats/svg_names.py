"""SVG namespaces and the qualified names PressToShape's reader and writer share."""

import xml.etree.ElementTree as ET

from presstoshape.formats.svg_page import PRESSTOSHAPE_NS

SVG_NS = "http://www.w3.org/2000/svg"
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
XLINK_NS = "http://www.w3.org/1999/xlink"
SODIPODI_NS = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
ET.register_namespace("", SVG_NS)
# Composite definitions live in PRESSTOSHAPE_NS, inside the result path's <metadata>: viewers don't render it
# and Inkscape keeps it.
ET.register_namespace("inkscape", INKSCAPE_NS)
ET.register_namespace("presstoshape", PRESSTOSHAPE_NS)
ET.register_namespace("sodipodi", SODIPODI_NS)
ET.register_namespace("xlink", XLINK_NS)
COMPOSITE = f"{{{PRESSTOSHAPE_NS}}}composite"
MODE = f"{{{PRESSTOSHAPE_NS}}}mode"
PART_MODES = ("add", "subtract", "intersect", "exclude")
GROUPMODE = f"{{{INKSCAPE_NS}}}groupmode"
LABEL = f"{{{INKSCAPE_NS}}}label"
# Inkscape marks locked objects and layers with sodipodi:insensitive="true".
INSENSITIVE = f"{{{SODIPODI_NS}}}insensitive"
NODETYPES = f"{{{SODIPODI_NS}}}nodetypes"
XLINK_HREF = f"{{{XLINK_NS}}}href"
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
SVG_PREFIX = f"{{{SVG_NS}}}"


def q(tag: str) -> str:
    return f"{{{SVG_NS}}}{tag}"
