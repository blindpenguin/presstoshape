"""Style of the selected shapes. Tool defaults live in view.set_tool_style."""

from dataclasses import fields, replace
from typing import Any

from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.shapes import GroupShape, ImageShape, Paint, Shape, Style, content_children, sanitized

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


def set_fill(session: Session, color: Paint) -> None:
    set_style(session, fill=color)


def set_stroke(session: Session, color: Paint) -> None:
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
        map_selected(session.state, lambda shape: restyle_shape(shape, **changes))


def restyled(style: Style, **changes: Any) -> Style:
    return sanitized(replace(style, **changes))


def restyle_shape(shape: Shape, **changes: Any) -> Shape:
    """`shape` with style `changes`. A group takes `opacity` as its own and hands every other field to the
    shapes inside it, as Inkscape and Illustrator do; the mask objects of a masked group keep their look."""
    if isinstance(shape, ImageShape):
        return (
            replace(shape, opacity=restyled(Style(), opacity=changes["opacity"]).opacity)
            if "opacity" in changes
            else shape
        )
    if not isinstance(shape, GroupShape):
        return replace(shape, style=restyled(shape.style, **changes))
    updated = shape
    if "opacity" in changes:
        updated = replace(updated, opacity=sanitized(Style(opacity=changes["opacity"])).opacity)
    for_children = {key: value for key, value in changes.items() if key != "opacity"}
    if for_children:
        masking = updated.masking
        updated = replace(
            updated,
            children=tuple(
                child if masking is not None and masking.is_mask(child.id) else restyle_shape(child, **for_children)
                for child in updated.children
            ),
        )
    return updated


def display_style(shape: Shape) -> Style:
    """The style the panel shows for `shape`: for a group, its first shape's (searching inside nested groups)
    with the group's own opacity."""
    if isinstance(shape, ImageShape):
        return Style(opacity=shape.opacity)
    if not isinstance(shape, GroupShape):
        return shape.style
    leaf = _first_leaf(shape)
    base = leaf.style if leaf is not None else Style()
    return replace(base, opacity=shape.opacity)


def _first_leaf(group: GroupShape) -> Shape | None:
    for child in content_children(group):
        leaf = _first_leaf(child) if isinstance(child, GroupShape) else child
        if leaf is not None:
            return leaf
    return None
