"""Style of the selected shapes. Tool defaults live in view.set_tool_style."""

from dataclasses import fields, replace
from typing import Any

from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.shapes import Style, sanitized

# Undo label per style field.
_LABELS = {
    "fill": N_("Change fill"),
    "stroke": N_("Change stroke"),
    "stroke_width": N_("Change stroke width"),
    "opacity": N_("Change opacity"),
    "fill_opacity": N_("Change fill opacity"),
    "stroke_opacity": N_("Change stroke opacity"),
    "fill_rule": N_("Change fill rule"),
    "cap": N_("Change line cap"),
    "join": N_("Change line join"),
    "miter_limit": N_("Change mitre limit"),
    "dashes": N_("Change dashes"),
    "dash_offset": N_("Change dash offset"),
}
# Fields edited with sliders and spin boxes: repeated steps merge into one undo step.
_MERGED = frozenset({"stroke_width", "opacity", "fill_opacity", "stroke_opacity", "miter_limit", "dash_offset"})
_FIELDS = frozenset(field.name for field in fields(Style))


def set_fill(session: Session, color: str | None) -> None:
    set_style(session, fill=color)


def set_stroke(session: Session, color: str | None) -> None:
    set_style(session, stroke=color)


def set_stroke_width(session: Session, width: float) -> None:
    set_style(session, stroke_width=width)


def set_style(session: Session, **changes: Any) -> None:
    """Changes style fields of every selected shape as one undo step; values are brought into range."""
    unknown = set(changes) - _FIELDS
    if unknown:
        raise ValueError(f"unknown style fields {sorted(unknown)}")
    if not changes or not session.state.selection:
        return
    (only, *rest) = changes
    label = _(_LABELS[only]) if not rest else _("Change style")
    merge_key = only if not rest and only in _MERGED else None
    with session.edit(label, merge_key):
        map_selected(session.state, lambda shape: replace(shape, style=restyled(shape.style, **changes)))


def restyled(style: Style, **changes: Any) -> Style:
    return sanitized(replace(style, **changes))
