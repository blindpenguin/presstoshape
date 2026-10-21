"""SVG conditional processing: `systemLanguage`, `requiredExtensions` and `<switch>`.

The user's languages come in as a parameter (formats/ knows nothing of the UI). `requiredFeatures` is ignored,
as browsers do since SVG 2 removed it; no extension is supported, so `requiredExtensions` never passes.
"""

import xml.etree.ElementTree as ET

from presstoshape.formats.svg_names import SVG_PREFIX

_DRAWABLE = frozenset(
    {
        "g",
        "use",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "path",
        "text",
        "svg",
        "image",
        "switch",
        "a",
        "foreignObject",
    }
)


def passes(element: ET.Element, languages: tuple[str, ...]) -> bool:
    if element.get("requiredExtensions") is not None:
        return False
    value = element.get("systemLanguage")
    if value is None:
        return True
    wanted = [language.lower() for language in languages]
    for tag in value.split(","):
        tag = tag.strip().lower()
        if tag and any(tag == language or tag.startswith(language + "-") for language in wanted):
            return True
    return False


def is_drawable(element: ET.Element) -> bool:
    tag = element.tag
    return isinstance(tag, str) and tag.startswith(SVG_PREFIX) and tag[len(SVG_PREFIX) :] in _DRAWABLE


def switch_choice(switch: ET.Element, languages: tuple[str, ...]) -> ET.Element | None:
    """The first drawable child whose conditions pass."""
    for child in switch:
        if is_drawable(child) and passes(child, languages):
            return child
    return None
