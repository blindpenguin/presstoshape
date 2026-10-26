"""The colour panel's edits: colours applied to the active paint (fill or stroke) of whatever the panel targets
(queries.colour_target), recent colours, and the eyedropper's pick-ups."""

from collections.abc import Callable
from dataclasses import fields, replace
from typing import Any

from presstoshape.editing import queries
from presstoshape.editing.operations import view
from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.operations.style import display_style, restyle_shape, restyled
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import AppState
from presstoshape.models.colours import RECENT_LIMIT, NumberMode, PaintSlot
from presstoshape.models.shapes import GroupShape, ImageShape, Paint, Shape, Style, flat_color, sanitized


class _Mixed:
    def __repr__(self) -> str:
        return "MIXED"


# The selected shapes don't agree on a paint.
MIXED = _Mixed()

_PAINT_LABELS = {"fill": N_("Change fill"), "stroke": N_("Change stroke")}


def target_style(state: AppState) -> Style:
    """The style the colour panel shows: the first selected shape's, the active tool's, or the current colour."""
    target = queries.colour_target(state)
    if target == "selection":
        painted = [shape for shape in queries.selected_shapes(state) if not isinstance(shape, ImageShape)]
        return display_style(painted[0])
    if target == "tool":
        return state.tool_styles[state.active_tool]
    return state.colours.current


def target_paint(state: AppState, slot: PaintSlot) -> Paint | _Mixed:
    """The paint in `slot` of the target, MIXED when selected shapes differ."""
    if queries.colour_target(state) != "selection":
        return getattr(target_style(state), slot)
    paints = [
        getattr(display_style(shape), slot)
        for shape in queries.selected_shapes(state)
        if not isinstance(shape, ImageShape)
    ]
    return paints[0] if all(paint == paints[0] for paint in paints) else MIXED


def _restyle(session: Session, label: str, merge_key: str | None = None, **changes: Any) -> None:
    state = session.state
    target = queries.colour_target(state)
    if target == "selection":
        with session.edit(label, merge_key):
            map_selected(state, lambda shape: restyle_shape(shape, **changes))
    elif target == "tool":
        view.set_tool_style(session, state.active_tool, **changes)
    elif target == "current":
        state.colours.current = restyled(state.colours.current, **changes)
        session.notify()


def _map_styles(session: Session, label: str, change: Callable[[Style], Style]) -> None:
    """Like _restyle, but `change` sees each shape's own style (swapping fill and stroke differs per shape)."""
    state = session.state
    target = queries.colour_target(state)
    if target == "selection":

        def each(shape: Shape) -> Shape:
            if isinstance(shape, ImageShape):
                return shape
            if isinstance(shape, GroupShape):
                masking = shape.masking
                children = tuple(
                    child if masking is not None and masking.is_mask(child.id) else each(child)
                    for child in shape.children
                )
                return replace(shape, children=children)
            return replace(shape, style=sanitized(change(shape.style)))

        with session.edit(label):
            map_selected(state, each)
    elif target == "tool":
        tool = state.active_tool
        state.tool_styles[tool] = sanitized(change(state.tool_styles[tool]))
        session.notify()
    elif target == "current":
        state.colours.current = sanitized(change(state.colours.current))
        session.notify()


def set_active_paint(session: Session, slot: PaintSlot) -> None:
    session.state.colours.active = slot
    session.notify()


@operation("colour.toggle_active", N_("Edit Fill or &Stroke"))
def toggle_active_paint(session: Session) -> None:
    colours = session.state.colours
    set_active_paint(session, "stroke" if colours.active == "fill" else "fill")


def apply_colour(session: Session, color: str, opacity: float | None = None, merge_key: str | None = None) -> None:
    """`color` (and `opacity`, if given) into the active paint of the target. Field steps pass a `merge_key`; they
    are remembered as recent colours when the edit finishes, not at every step."""
    slot = session.state.colours.active
    changes: dict[str, Any] = {slot: color}
    if opacity is not None:
        changes[f"{slot}_opacity"] = opacity
    # Remembered first, so the restyle's one notify covers it: a second refresh is costly on large documents.
    if merge_key is None and _can_paint(session):
        _remembered(session.state, color)
    _restyle(session, _(_PAINT_LABELS[slot]), merge_key, **changes)


def apply_opacity(session: Session, opacity: float, merge_key: str | None = None) -> None:
    slot = session.state.colours.active
    label = N_("Change fill opacity") if slot == "fill" else N_("Change stroke opacity")
    _restyle(session, _(label), merge_key, **{f"{slot}_opacity": opacity})


def apply_sampled_colour(session: Session, color: str) -> None:
    """A colour read from the canvas: the active paint takes it, its opacity stays."""
    apply_colour(session, color)


def _can_paint(session: Session) -> bool:
    return queries.colour_target(session.state) != "disabled"


@operation("colour.none", N_("&No Paint"), can_run=_can_paint)
def set_paint_none(session: Session) -> None:
    slot = session.state.colours.active
    _restyle(session, _(_PAINT_LABELS[slot]), **{slot: None})


@operation("colour.swap", N_("S&wap Fill and Stroke"), can_run=_can_paint)
def swap_paints(session: Session) -> None:
    _map_styles(
        session,
        _("Swap fill and stroke"),
        lambda style: replace(
            style,
            fill=style.stroke,
            stroke=style.fill,
            fill_opacity=style.stroke_opacity,
            stroke_opacity=style.fill_opacity,
        ),
    )


@operation("colour.default", N_("&Default Fill and Stroke"), can_run=_can_paint)
def default_paints(session: Session) -> None:
    default = Style()
    _restyle(
        session,
        _("Default fill and stroke"),
        fill=default.fill,
        stroke=default.stroke,
        fill_opacity=default.fill_opacity,
        stroke_opacity=default.stroke_opacity,
    )


def pick_up_style(session: Session, source: Style) -> None:
    """Eyedropper: the selection takes `source` as a whole; without a selection the target takes its fill and
    stroke. The picked colours become recent colours."""
    _remembered(session.state, flat_color(source.fill), flat_color(source.stroke))
    if queries.colour_target(session.state) == "selection":
        _restyle(session, _("Pick up style"), **{field.name: getattr(source, field.name) for field in fields(Style)})
    else:
        _restyle(
            session,
            _("Pick up style"),
            fill=source.fill,
            stroke=source.stroke,
            fill_opacity=source.fill_opacity,
            stroke_opacity=source.stroke_opacity,
        )


def _remembered(state: AppState, *colors: str | None) -> bool:
    """Puts `colors` first among the recent colours (first argument first); whether that changed them."""
    picked = [color.lower() for color in colors if color is not None]
    colours = state.colours
    recent = tuple(dict.fromkeys([*picked, *colours.recent]))[:RECENT_LIMIT]
    if recent == colours.recent:
        return False
    colours.recent = recent
    return True


def remember_colour(session: Session, *colors: str | None) -> None:
    if _remembered(session.state, *colors):
        session.notify()


def clear_recent_colours(session: Session) -> None:
    session.state.colours.recent = ()
    session.notify()


def set_number_mode(session: Session, mode: NumberMode) -> None:
    session.state.colours.numbers = mode
    session.notify()
