"""Live corners in SVG: the path's `d` is the rounded outline every viewer draws, and a
`<metadata><presstoshape:corners>` child keeps the original path data, its corner nodes and roundings. Reading
restores them only while they still produce the element's `d`; a path edited elsewhere opens as drawn."""

import math
import xml.etree.ElementTree as ET
from dataclasses import replace

from presstoshape.formats.svg_names import CORNERS, q
from presstoshape.formats.svg_page import number_text
from presstoshape.formats.svg_values import parse_path_data
from presstoshape.geometry import corners
from presstoshape.geometry.affine import Affine, apply
from presstoshape.geometry.segments import transform_segments
from presstoshape.models.shapes import CORNER_KINDS, Close, Rounding, Segment

Segments = tuple[Segment, ...]

# How far (user units, scaled with the element) a restored outline may be from `d`: what number formatting loses.
_TOLERANCE = 0.01


def metadata(segments: Segments, path_d) -> ET.Element | None:
    """`<metadata>` for a path with live corners, or None when it has none."""
    if not corners.has_rounding(segments):
        return None
    meta = ET.Element(q("metadata"))
    flags = [str(i) for i, s in enumerate(segments) if getattr(s, "corner", False)]
    roundings = [
        f"{i}:{s.rounding.kind}:{number_text(s.rounding.radius)}"
        for i, s in enumerate(segments)
        if getattr(s, "rounding", None) is not None
    ]
    attrs = {"d": path_d(segments), "roundings": " ".join(roundings)}
    if flags:
        attrs["corners"] = " ".join(flags)
    ET.SubElement(meta, CORNERS, attrs)
    return meta


def _decoded(data: ET.Element, scale: float) -> Segments:
    """The stored path with its flags and roundings; raises ValueError on anything malformed."""
    segments, cut = parse_path_data(data.get("d", ""))
    if cut or not segments:
        raise ValueError("bad path data")
    out = list(segments)

    def node(text: str) -> int:
        index = int(text)
        if not 0 <= index < len(out) or isinstance(out[index], Close):
            raise ValueError("not a node")
        return index

    for text in (data.get("corners") or "").split():
        index = node(text)
        out[index] = replace(out[index], corner=True)
    for item in (data.get("roundings") or "").split():
        index_text, kind, radius_text = item.split(":")
        radius = float(radius_text) * scale
        if kind not in CORNER_KINDS or not math.isfinite(radius) or radius <= 0:
            raise ValueError("bad rounding")
        index = node(index_text)
        out[index] = replace(out[index], rounding=Rounding(radius, kind))
    return tuple(out)


def _close(a: Segments, b: Segments, tolerance: float) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if type(x) is not type(y):
            return False
        for name in ("c1x", "c1y", "c2x", "c2y", "x", "y"):
            if hasattr(x, name) and abs(getattr(x, name) - getattr(y, name)) > tolerance:
                return False
    return True


def restored(element: ET.Element, drawn: Segments, m: Affine) -> Segments | None:
    """The live path behind `element` (with `m` baked in like `drawn`), or None when there is none or it no longer
    produces the drawn outline."""
    data = element.find(f"{q('metadata')}/{CORNERS}")
    if data is None:
        return None
    scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
    try:
        segments = _decoded(data, scale)
    except ValueError:
        return None
    segments = transform_segments(segments, lambda x, y: apply(m, x, y))
    if not _close(corners.rounded(segments), drawn, _TOLERANCE * max(scale, 1.0)):
        return None
    return segments
