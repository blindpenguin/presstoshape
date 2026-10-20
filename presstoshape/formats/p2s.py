"""PressToShape's native .p2s format: a ZIP with the document as JSON. Field by field and type by type on
purpose, so renaming a model field never silently changes what files contain. See docs/file-format.md."""

import io
import json
import math
import zipfile
from dataclasses import dataclass, field
from typing import Any, get_args

from presstoshape.formats.p2s_migrations import CURRENT_VERSION, upgrade
from presstoshape.geometry import units
from presstoshape.geometry.boxes import Point
from presstoshape.i18n import _
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    FillRule,
    GroupShape,
    LineCap,
    LineJoin,
    LineTo,
    MoveTo,
    PartMode,
    PathShape,
    RectShape,
    Segment,
    Shape,
    Style,
    TextAnchor,
    TextShape,
    Transform,
    children_of,
    sanitized,
)

MIMETYPE = "application/x-presstoshape"
FORMAT_NAME = "presstoshape"
PART_MODES = ("add", "subtract", "intersect", "exclude")
_MAX_TEXT = 100_000
_MAX_COLOR = 64
# Limits against hostile archives; far above anything a real drawing needs.
_MAX_DOCUMENT_BYTES = 64 * 1024 * 1024
_MAX_PREVIEW_BYTES = 8 * 1024 * 1024
_READ_CHUNK = 1024 * 1024
# Fixed entry timestamps, so saving the same drawing twice gives the same bytes.
_ENTRY_DATE = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class SavedState:
    """Working state kept in .p2s files next to the document. None / empty means "not stored"."""

    zoom_percent: int | None = None
    view_center: Point | None = None
    tool_styles: dict[Tool, Style] = field(default_factory=dict)
    font_size: float | None = None
    new_part_mode: PartMode | None = None
    pencil_smoothing: int | None = None
    selection: frozenset[int] = frozenset()
    selected_layer: int | None = None
    edit_path: tuple[int, ...] = ()


class P2sError(ValueError):
    """Any reason a .p2s file can't be read; the message is meant for the status bar."""


# --- encoding -----------------------------------------------------------------------------------


# Numbers are always written as floats: an int coming back as a float would otherwise change the next save.
_number = float


_DEFAULT_STYLE = Style()


def encode_style(style: Style) -> dict[str, Any]:
    """fill, stroke and stroke_width always; the fields added in version 4 only when they differ from the
    default, so plain shapes stay as compact as before."""
    fields: dict[str, Any] = {"fill": style.fill, "stroke": style.stroke, "stroke_width": _number(style.stroke_width)}
    for key in ("opacity", "fill_opacity", "stroke_opacity", "miter_limit", "dash_offset"):
        if getattr(style, key) != getattr(_DEFAULT_STYLE, key):
            fields[key] = _number(getattr(style, key))
    for key in ("fill_rule", "cap", "join"):
        if getattr(style, key) != getattr(_DEFAULT_STYLE, key):
            fields[key] = getattr(style, key)
    if style.dashes:
        fields["dashes"] = [_number(value) for value in style.dashes]
    return fields


def _encode_segment(segment: Segment) -> list[Any]:
    match segment:
        case MoveTo(x=x, y=y):
            return ["M", _number(x), _number(y)]
        case LineTo(x=x, y=y):
            return ["L", _number(x), _number(y)]
        case CubicTo(c1x=c1x, c1y=c1y, c2x=c2x, c2y=c2y, x=x, y=y):
            return ["C", *map(_number, (c1x, c1y, c2x, c2y, x, y))]
        case Close():
            return ["Z"]


def _numbers(**values: float) -> dict[str, float]:
    return {key: _number(value) for key, value in values.items()}


def encode_shape(shape: Shape) -> dict[str, Any]:
    if isinstance(shape, GroupShape):
        # No style and no transform: a group has no paint of its own and its children carry the transforms.
        fields: dict[str, Any] = {
            "type": "group",
            "id": shape.id,
            "children": [encode_shape(child) for child in shape.children],
        }
        if shape.opacity != 1:
            fields["opacity"] = _number(shape.opacity)
        return fields
    match shape:
        case RectShape(x=x, y=y, width=width, height=height, rx=rx, ry=ry):
            fields = {"type": "rect", "id": shape.id, **_numbers(x=x, y=y, width=width, height=height)}
            if rx or ry:
                fields |= _numbers(rx=rx, ry=ry)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            fields = {"type": "ellipse", "id": shape.id, **_numbers(cx=cx, cy=cy, rx=rx, ry=ry)}
        case PathShape(segments=segments):
            fields = {"type": "path", "id": shape.id, "segments": [_encode_segment(segment) for segment in segments]}
        case TextShape(x=x, y=y, text=text, font_size=font_size):
            fields = {"type": "text", "id": shape.id, **_numbers(x=x, y=y), "text": text}
            fields["font_size"] = _number(font_size)
            if shape.anchor != "start":
                fields["anchor"] = shape.anchor
        case CompositeShape(parts=parts, modes=modes):
            fields = {
                "type": "composite",
                "id": shape.id,
                "parts": [encode_shape(part) for part in parts],
                "modes": list(modes),
            }
    fields["style"] = encode_style(shape.style)
    if shape.transform != IDENTITY_TRANSFORM:
        fields["transform"] = [_number(value) for value in shape.transform]
    return fields


def encode_document(document: Document) -> dict[str, Any]:
    return {
        **_numbers(width=document.width, height=document.height),
        "unit": document.unit,
        "dpi": _number(document.dpi),
        "next_id": document.next_id,
        "layers": [
            {"name": layer.name, "visible": layer.visible, "shapes": [encode_shape(shape) for shape in layer.shapes]}
            for layer in document.layers
        ],
    }


# --- decoding ---------------------------------------------------------------------------------------
# Every reader takes the JSON path of the value (e.g. "document.layers[0].shapes[3]") for its error message.


def _one_of(choices: tuple[str, ...]) -> str:
    return _("should be one of {choices}").format(choices=", ".join(choices))


def _damaged(where: str, problem: str) -> P2sError:
    return P2sError(_("damaged file: {where} {problem}").format(where=where, problem=problem))


def read_object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _damaged(where, _("should be an object"))
    return value


def read_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise _damaged(where, _("should be a list"))
    return value


def _field(fields: dict[str, Any], key: str, where: str) -> Any:
    if key not in fields:
        raise _damaged(where, _("is missing {key}").format(key=repr(key)))
    return fields[key]


def read_number(value: Any, where: str, minimum: float | None = None) -> float:
    # bool is an int subclass; true/false in place of a number is damage, not 1/0.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _damaged(where, _("should be a finite number"))
    if minimum is not None and value < minimum:
        raise _damaged(where, _("should be at least {minimum}").format(minimum=minimum))
    return float(value)


def read_int(value: Any, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _damaged(where, _("should be a whole number of at least {minimum}").format(minimum=minimum))
    return value


def read_string(value: Any, where: str, max_length: int = _MAX_TEXT) -> str:
    if not isinstance(value, str) or len(value) > max_length:
        raise _damaged(where, _("should be text"))
    return value


def _number_field(fields: dict[str, Any], key: str, where: str, minimum: float | None = None) -> float:
    return read_number(_field(fields, key, where), f"{where}.{key}", minimum)


def _color(value: Any, where: str) -> str | None:
    return None if value is None else read_string(value, where, _MAX_COLOR)


def _optional_number(
    fields: dict[str, Any],
    key: str,
    where: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if key not in fields:
        return default
    value = read_number(fields[key], f"{where}.{key}", minimum)
    if maximum is not None and value > maximum:
        raise _damaged(f"{where}.{key}", _("should be at most {maximum}").format(maximum=maximum))
    return value


def _optional_choice(fields: dict[str, Any], key: str, where: str, choices: tuple[str, ...], default: str) -> Any:
    value = fields.get(key, default)
    if value not in choices:
        raise _damaged(f"{where}.{key}", _one_of(choices))
    return value


def decode_style(value: Any, where: str) -> Style:
    fields = read_object(value, where)
    dashes = tuple(
        read_number(item, f"{where}.dashes[{index}]", minimum=0.0)
        for index, item in enumerate(read_list(fields.get("dashes", []), f"{where}.dashes"))
    )
    style = Style(
        fill=_color(_field(fields, "fill", where), f"{where}.fill"),
        stroke=_color(_field(fields, "stroke", where), f"{where}.stroke"),
        stroke_width=_number_field(fields, "stroke_width", where, minimum=0.0),
        opacity=_optional_number(fields, "opacity", where, 1.0, minimum=0.0, maximum=1.0),
        fill_opacity=_optional_number(fields, "fill_opacity", where, 1.0, minimum=0.0, maximum=1.0),
        stroke_opacity=_optional_number(fields, "stroke_opacity", where, 1.0, minimum=0.0, maximum=1.0),
        fill_rule=_optional_choice(fields, "fill_rule", where, get_args(FillRule), "nonzero"),
        cap=_optional_choice(fields, "cap", where, get_args(LineCap), "butt"),
        join=_optional_choice(fields, "join", where, get_args(LineJoin), "miter"),
        miter_limit=_optional_number(fields, "miter_limit", where, 4.0, minimum=1.0),
        dashes=dashes,
        dash_offset=_optional_number(fields, "dash_offset", where, 0.0),
    )
    # Dash lists other programs couldn't draw (odd length, all zero) are normalized the way SVG does.
    return sanitized(style)


def _decode_transform(fields: dict[str, Any], where: str) -> Transform:
    if "transform" not in fields:
        return IDENTITY_TRANSFORM
    values = read_list(fields["transform"], f"{where}.transform")
    if len(values) != 6:
        raise _damaged(f"{where}.transform", _("should have 6 numbers"))
    return tuple(read_number(value, f"{where}.transform[{index}]") for index, value in enumerate(values))


_SEGMENT_SIZES = {"M": 2, "L": 2, "C": 6, "Z": 0}


def _decode_segment(value: Any, where: str) -> Segment:
    items = read_list(value, where)
    if not items or items[0] not in _SEGMENT_SIZES or len(items) != _SEGMENT_SIZES[items[0]] + 1:
        raise _damaged(where, _('should be a path segment like ["L", x, y]'))
    numbers = [read_number(item, f"{where}[{index}]") for index, item in enumerate(items[1:], start=1)]
    match items[0]:
        case "M":
            return MoveTo(*numbers)
        case "L":
            return LineTo(*numbers)
        case "C":
            return CubicTo(*numbers)
        case _:
            return Close()


def decode_shape(value: Any, where: str) -> Shape:
    fields = read_object(value, where)
    shape_type = _field(fields, "type", where)
    shape_id = read_int(_field(fields, "id", where), f"{where}.id", minimum=0)
    if shape_type == "group":
        child_values = read_list(_field(fields, "children", where), f"{where}.children")
        if not child_values:
            raise _damaged(f"{where}.children", _("should not be empty"))
        children = tuple(decode_shape(child, f"{where}.children[{index}]") for index, child in enumerate(child_values))
        opacity = _optional_number(fields, "opacity", where, 1.0, minimum=0.0, maximum=1.0)
        return GroupShape(shape_id, children, opacity)
    style = decode_style(_field(fields, "style", where), f"{where}.style")
    transform = _decode_transform(fields, where)
    match shape_type:
        case "rect":
            return RectShape(
                shape_id,
                _number_field(fields, "x", where),
                _number_field(fields, "y", where),
                _number_field(fields, "width", where, minimum=0.0),
                _number_field(fields, "height", where, minimum=0.0),
                style,
                transform,
                rx=_optional_number(fields, "rx", where, 0.0, minimum=0.0),
                ry=_optional_number(fields, "ry", where, 0.0, minimum=0.0),
            )
        case "ellipse":
            return EllipseShape(
                shape_id,
                _number_field(fields, "cx", where),
                _number_field(fields, "cy", where),
                _number_field(fields, "rx", where, minimum=0.0),
                _number_field(fields, "ry", where, minimum=0.0),
                style,
                transform,
            )
        case "path":
            items = read_list(_field(fields, "segments", where), f"{where}.segments")
            segments = tuple(_decode_segment(item, f"{where}.segments[{index}]") for index, item in enumerate(items))
            return PathShape(shape_id, segments, style, transform)
        case "text":
            return TextShape(
                shape_id,
                _number_field(fields, "x", where),
                _number_field(fields, "y", where),
                read_string(_field(fields, "text", where), f"{where}.text"),
                _number_field(fields, "font_size", where, minimum=0.1),
                style,
                transform,
                anchor=_optional_choice(fields, "anchor", where, get_args(TextAnchor), "start"),
            )
        case "composite":
            part_values = read_list(_field(fields, "parts", where), f"{where}.parts")
            mode_values = read_list(_field(fields, "modes", where), f"{where}.modes")
            if not part_values or len(mode_values) != len(part_values):
                raise _damaged(where, _("should have parts and one mode per part"))
            for index, mode in enumerate(mode_values):
                if mode not in PART_MODES:
                    raise _damaged(f"{where}.modes[{index}]", _one_of(PART_MODES))
            parts = tuple(decode_shape(part, f"{where}.parts[{index}]") for index, part in enumerate(part_values))
            return CompositeShape(shape_id, parts, tuple(mode_values), style, transform)
        case _:
            raise _damaged(f"{where}.type", _("is an unknown shape type {type}").format(type=repr(shape_type)))


def _all_ids(shapes: list[Shape]) -> list[int]:
    ids = []
    for shape in shapes:
        ids.append(shape.id)
        ids.extend(_all_ids(list(children_of(shape))))
    return ids


def decode_document(value: Any, where: str = "document") -> Document:
    fields = read_object(value, where)
    layer_values = read_list(_field(fields, "layers", where), f"{where}.layers")
    layers = []
    for index, layer_value in enumerate(layer_values):
        layer_where = f"{where}.layers[{index}]"
        layer_fields = read_object(layer_value, layer_where)
        visible = _field(layer_fields, "visible", layer_where)
        if not isinstance(visible, bool):
            raise _damaged(f"{layer_where}.visible", _("should be true or false"))
        shape_values = read_list(_field(layer_fields, "shapes", layer_where), f"{layer_where}.shapes")
        shapes = [decode_shape(item, f"{layer_where}.shapes[{number}]") for number, item in enumerate(shape_values)]
        name = read_string(_field(layer_fields, "name", layer_where), f"{layer_where}.name")
        layers.append(Layer(name, visible, shapes))
    if not layers:
        raise _damaged(f"{where}.layers", _("should have at least one layer"))
    ids = [shape_id for layer in layers for shape_id in _all_ids(layer.shapes)]
    if len(ids) != len(set(ids)):
        raise _damaged(where, _("uses a shape id twice"))
    next_id = read_int(_field(fields, "next_id", where), f"{where}.next_id", minimum=0)
    unit = _field(fields, "unit", where)
    if unit not in units.UNITS:
        raise _damaged(f"{where}.unit", _one_of(units.UNITS))
    dpi = _number_field(fields, "dpi", where, minimum=units.MIN_DPI)
    if dpi > units.MAX_DPI:
        raise _damaged(f"{where}.dpi", _("should be at most {maximum}").format(maximum=units.MAX_DPI))
    return Document(
        width=_number_field(fields, "width", where, minimum=0.1),
        height=_number_field(fields, "height", where, minimum=0.1),
        layers=layers,
        # A hand-edited next_id below an existing id would hand out duplicates later.
        next_id=max([next_id, *(shape_id + 1 for shape_id in ids)]),
        unit=unit,
        dpi=dpi,
    )


# --- working state ---------------------------------------------------------------------------------


def encode_state(state: SavedState) -> dict[str, Any]:
    view: dict[str, Any] = {}
    if state.zoom_percent is not None:
        view["zoom_percent"] = state.zoom_percent
    if state.view_center is not None:
        view["center"] = [_number(state.view_center[0]), _number(state.view_center[1])]
    styles = {tool.name.lower(): encode_style(style) for tool, style in state.tool_styles.items()}
    tools: dict[str, Any] = {"styles": styles}
    if state.font_size is not None:
        tools["font_size"] = _number(state.font_size)
    if state.new_part_mode is not None:
        tools["new_part_mode"] = state.new_part_mode
    if state.pencil_smoothing is not None:
        tools["pencil_smoothing"] = state.pencil_smoothing
    fields: dict[str, Any] = {"view": view, "tools": tools, "selection": sorted(state.selection)}
    if state.selected_layer is not None:
        fields["selected_layer"] = state.selected_layer
    fields["edit_path"] = list(state.edit_path)
    return fields


def decode_state(value: Any, where: str = "state") -> SavedState:
    fields = read_object(value, where)
    view = read_object(fields.get("view", {}), f"{where}.view")
    tools = read_object(fields.get("tools", {}), f"{where}.tools")
    zoom = view.get("zoom_percent")
    center = view.get("center")
    if center is not None:
        items = read_list(center, f"{where}.view.center")
        if len(items) != 2:
            raise _damaged(f"{where}.view.center", _("should have 2 numbers"))
        center = (read_number(items[0], f"{where}.view.center[0]"), read_number(items[1], f"{where}.view.center[1]"))
    styles = {}
    known_tools = {tool.name.lower(): tool for tool in Tool}
    for name, style in read_object(tools.get("styles", {}), f"{where}.tools.styles").items():
        # A tool from a newer version is skipped rather than refused.
        if name in known_tools:
            styles[known_tools[name]] = decode_style(style, f"{where}.tools.styles.{name}")
    font_size = tools.get("font_size")
    mode = tools.get("new_part_mode")
    smoothing = tools.get("pencil_smoothing")
    if smoothing is not None:
        smoothing = read_int(smoothing, f"{where}.tools.pencil_smoothing")
        if smoothing > 100:
            raise _damaged(f"{where}.tools.pencil_smoothing", _("should be at most {maximum}").format(maximum=100))
    if mode is not None and mode not in PART_MODES:
        raise _damaged(f"{where}.tools.new_part_mode", _one_of(PART_MODES))
    selection = read_list(fields.get("selection", []), f"{where}.selection")
    edit_path = read_list(fields.get("edit_path", []), f"{where}.edit_path")
    layer = fields.get("selected_layer")
    return SavedState(
        zoom_percent=None if zoom is None else read_int(zoom, f"{where}.view.zoom_percent", minimum=1),
        view_center=center,
        tool_styles=styles,
        font_size=None if font_size is None else read_number(font_size, f"{where}.tools.font_size", minimum=0.1),
        new_part_mode=mode,
        pencil_smoothing=smoothing,
        selection=frozenset(read_int(item, f"{where}.selection[{index}]", 0) for index, item in enumerate(selection)),
        selected_layer=None if layer is None else read_int(layer, f"{where}.selected_layer"),
        edit_path=tuple(read_int(item, f"{where}.edit_path[{index}]", 0) for index, item in enumerate(edit_path)),
    )


# --- archive ------------------------------------------------------------------------------------------


def _entry(name: str, compression: int) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ENTRY_DATE)
    info.compress_type = compression
    return info


def write_p2s(document: Document, state: SavedState, preview: bytes | None, app_version: str) -> bytes:
    payload = {
        "format": FORMAT_NAME,
        "format_version": CURRENT_VERSION,
        "app_version": app_version,
        "document": encode_document(document),
        "state": encode_state(state),
    }
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        # First and uncompressed, so the type can be told from the file's first bytes (OpenDocument convention).
        archive.writestr(_entry("mimetype", zipfile.ZIP_STORED), MIMETYPE)
        archive.writestr(_entry("document.json", zipfile.ZIP_DEFLATED), text)
        if preview is not None:
            archive.writestr(_entry("preview.png", zipfile.ZIP_STORED), preview)
    return buffer.getvalue()


def _read_entry(archive: zipfile.ZipFile, name: str, limit: int) -> bytes:
    """Reads in chunks and stops at `limit`: the size an archive declares can't be trusted."""
    if archive.getinfo(name).file_size > limit:
        raise P2sError(_("damaged file: {name} is too large").format(name=name))
    chunks, total = [], 0
    with archive.open(name) as entry:
        while chunk := entry.read(_READ_CHUNK):
            total += len(chunk)
            if total > limit:
                raise P2sError(_("damaged file: {name} is too large").format(name=name))
            chunks.append(chunk)
    return b"".join(chunks)


def _reject_constant(name: str) -> None:
    raise P2sError(_("damaged file: document.json contains {value}").format(value=name))


def read_p2s(data: bytes) -> tuple[Document, SavedState]:
    """Raises P2sError with a user-readable reason for anything that isn't a readable .p2s file."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise P2sError(_("not a PressToShape file")) from None
    with archive:
        names = archive.namelist()
        try:
            if not names or names[0] != "mimetype" or _read_entry(archive, "mimetype", 100) != MIMETYPE.encode():
                raise P2sError(_("not a PressToShape file"))
            if "document.json" not in names:
                raise P2sError(_("damaged file: document.json is missing"))
            raw = _read_entry(archive, "document.json", _MAX_DOCUMENT_BYTES)
        except (zipfile.BadZipFile, OSError, EOFError) as error:
            raise P2sError(_("damaged file: {error}").format(error=error)) from None
    try:
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise P2sError(_("damaged file: document.json isn't valid JSON ({error})").format(error=error)) from None
    payload = read_object(payload, "document.json")
    if payload.get("format") != FORMAT_NAME:
        raise P2sError(_("not a PressToShape file"))
    version = read_int(payload.get("format_version"), "format_version", minimum=1)
    if version > CURRENT_VERSION:
        message = _(
            "made with a newer PressToShape (file format {version}, this version reads up to {supported});"
            " please update PressToShape"
        )
        raise P2sError(message.format(version=version, supported=CURRENT_VERSION))
    payload = upgrade(payload, version)
    return decode_document(payload.get("document")), decode_state(payload.get("state", {}))


def read_preview(data: bytes) -> bytes | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "preview.png" not in archive.namelist():
                return None
            return _read_entry(archive, "preview.png", _MAX_PREVIEW_BYTES)
    except (zipfile.BadZipFile, P2sError):
        return None
