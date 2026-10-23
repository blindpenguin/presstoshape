"""Groups: bundle the selected shapes into one object and dissolve groups again."""

from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import new_id, prune_selection
from presstoshape.editing.operations._masking import released_children
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _, ngettext, pgettext
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import GroupShape, ImageShape, Shape, sanitized


def _can_group(session: Session) -> bool:
    state = session.state
    # Composite parts are outlines; a group can't be one.
    return bool(queries.selected_shapes(state)) and containers.edited_composite(state) is None


def _selected_groups(state: AppState) -> list[GroupShape]:
    return [shape for shape in queries.selected_shapes(state) if isinstance(shape, GroupShape)]


def _has_group(session: Session) -> bool:
    return bool(_selected_groups(session.state))


@operation("object.group", N_("&Group"), can_run=_can_group)
def group(session: Session) -> None:
    """Puts the selected shapes, in their stacking order, into one group where the top-most of them was."""
    state = session.state
    if not _can_group(session):
        return
    targets = queries.selected_shapes(state)
    target_ids = {shape.id for shape in targets}
    top_id = targets[-1].id
    with session.edit(pgettext("command", "Group")):
        grouped = GroupShape(new_id(state), tuple(targets))

        def regroup(shapes: list[Shape]) -> list[Shape]:
            return [
                grouped if shape.id == top_id else shape
                for shape in shapes
                if shape.id == top_id or shape.id not in target_ids
            ]

        containers.change_container(state, regroup)
        state.selection = {grouped.id}
        count = len(targets)
        state.status_message = ngettext("Grouped {count} object", "Grouped {count} objects", count).format(count=count)


@operation("object.ungroup", N_("&Ungroup"), can_run=_has_group)
def ungroup(session: Session) -> None:
    """Replaces each selected group by its shapes, in place. A group's opacity moves into each of them; a masked
    group is released like Release Clipping Mask / Release Opacity Mask."""
    state = session.state
    groups = {group.id: group for group in _selected_groups(state)}
    if not groups:
        return
    with session.edit(_("Ungroup")):
        released = {
            group_id: [with_opacity(child, group.opacity) for child in released_children(group)]
            for group_id, group in groups.items()
        }

        def unpack(shapes: list[Shape]) -> list[Shape]:
            result: list[Shape] = []
            for shape in shapes:
                result.extend(released.get(shape.id, [shape]))
            return result

        containers.change_container(state, unpack)
        state.selection = {child.id for children in released.values() for child in children}
        prune_selection(state)
        state.status_message = _("Ungrouped")


def with_opacity(shape: Shape, factor: float) -> Shape:
    """`shape` made `factor` times as opaque: a group through its own opacity, other shapes through their style."""
    if factor >= 1:
        return shape
    if isinstance(shape, GroupShape):
        return replace(shape, opacity=min(1.0, max(0.0, shape.opacity * factor)))
    if isinstance(shape, ImageShape):
        return replace(shape, opacity=min(1.0, max(0.0, shape.opacity * factor)))
    return replace(shape, style=sanitized(replace(shape.style, opacity=shape.style.opacity * factor)))
