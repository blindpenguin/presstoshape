"""Validation of presentation property values from attributes, style sheets and inline styles.

An invalid value is ignored by the cascade (the property keeps what lower layers or inheritance gave it). Attribute
values are case-sensitive, CSS values are not; the returned text is canonical, so the reader compares plain strings.
"""

import re
from functools import lru_cache

import svgelements as se

from presstoshape.formats import svg_lengths

_HEX_COLOR = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
_COLOR_FUNCTION = re.compile(r"(?:rgba?|hsla?)\(([-+0-9.%a-zA-Z\s,/]*)\)", re.IGNORECASE)
_OPAQUE_BLACK = 255
_ENUMS = {
    "fill-rule": ("nonzero", "evenodd"),
    "stroke-linecap": ("butt", "round", "square"),
    "stroke-linejoin": ("miter", "round", "bevel", "miter-clip", "arcs"),
    "text-anchor": ("start", "middle", "end"),
    "visibility": ("visible", "hidden", "collapse"),
    "overflow": ("visible", "hidden", "scroll", "auto"),
    "display": (
        "inline",
        "block",
        "list-item",
        "run-in",
        "compact",
        "marker",
        "table",
        "inline-table",
        "table-row-group",
        "table-header-group",
        "table-footer-group",
        "table-row",
        "table-column-group",
        "table-column",
        "table-cell",
        "table-caption",
        "none",
    ),
}
_NON_NEGATIVE_LENGTHS = ("stroke-width", "font-size")
_FONT_SIZE_KEYWORDS = ("xx-small", "x-small", "small", "medium", "large", "x-large", "xx-large", "larger", "smaller")
_OPACITIES = ("opacity", "fill-opacity", "stroke-opacity")
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


@lru_cache(maxsize=4096)
def normalize(name: str, value: str, css: bool) -> str | None:
    """The value in canonical form, or None when it is invalid for the property. Properties this module doesn't
    know pass through unchanged; `inherit` is the cascade's business and is accepted everywhere."""
    value = value.strip()
    if value == "inherit":
        return value
    if name in ("fill", "stroke"):
        return _paint(value, css)
    if name == "color":
        return _color_or_current(value, css)
    if name in _NON_NEGATIVE_LENGTHS:
        return _length(value, css, non_negative=True, keywords=_FONT_SIZE_KEYWORDS if name == "font-size" else ())
    if name == "stroke-dashoffset":
        return _length(value, css)
    if name == "stroke-dasharray":
        return _dasharray(value, css)
    if name in _OPACITIES:
        return _opacity(value)
    if name == "stroke-miterlimit":
        return _miter_limit(value)
    if name in _ENUMS:
        keyword = value.lower() if css else value
        return keyword if keyword in _ENUMS[name] else None
    return value


def is_color(value: str) -> bool:
    """A colour keyword, hex colour or rgb()/hsl() function. System colours (ActiveBorder, …) aren't valid."""
    if value.startswith("#"):
        return _HEX_COLOR.fullmatch(value) is not None
    function = _COLOR_FUNCTION.fullmatch(value)
    if function is not None:
        return 3 <= len(re.split(r"[\s,/]+", function.group(1).strip())) <= 4
    if not value.isalpha():
        return False
    # svgelements reads an unknown word as opaque black, so only "black" itself may produce that.
    return value.lower() in ("black", "transparent") or se.Color(value).value != _OPAQUE_BLACK


def _color_or_current(value: str, css: bool) -> str | None:
    if value.lower() == "currentcolor" and (css or value == "currentColor"):
        return "currentColor"
    return value if is_color(value) else None


def _paint(value: str, css: bool) -> str | None:
    if value.startswith("url("):
        end = value.find(")")
        fallback = value[end + 1 :].strip() if end > 0 else None
        if fallback is None:
            return None
        return value if not fallback else _fallback(value[: end + 1], fallback, css)
    keyword = value.lower() if css else value
    if keyword == "none":
        return "none"
    return _color_or_current(value, css)


def _fallback(reference: str, fallback: str, css: bool) -> str | None:
    paint = "none" if (fallback.lower() if css else fallback) == "none" else _color_or_current(fallback, css)
    return f"{reference} {paint}" if paint is not None else None


def _length(value: str, css: bool, non_negative: bool = False, keywords: tuple[str, ...] = ()) -> str | None:
    if css and value.lower() in keywords or value in keywords:
        return value.lower() if css else value
    parsed = svg_lengths.parse(value, css)
    if parsed is None or (non_negative and parsed[0] < 0):
        return None
    return f"{parsed[0]!r}{parsed[1]}"


def _dasharray(value: str, css: bool) -> str | None:
    if (value.lower() if css else value) == "none":
        return "none"
    items = [item for item in re.split(r"[\s,]+", value) if item]
    normalized = [_length(item, css, non_negative=True) for item in items]
    if not items or None in normalized:
        return None
    return " ".join(item for item in normalized if item is not None)


def _opacity(value: str) -> str | None:
    number = value[:-1] if value.endswith("%") else value
    return value if _NUMBER.fullmatch(number) else None


def _miter_limit(value: str) -> str | None:
    if _NUMBER.fullmatch(value) is None or float(value) < 1:
        return None
    return value
