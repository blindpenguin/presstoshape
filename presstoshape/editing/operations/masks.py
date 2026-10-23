"""Clipping masks and opacity masks: a group whose mask objects cut or fade the rest of its shapes."""

from dataclasses import replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import new_id, prune_selection
from presstoshape.editing.operations._masking import released_children
from presstoshape.editing.operations.groups import with_opacity
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import GroupShape, ImageShape, Masking, MaskType, Shape


def _selected_masked(state: AppState, clip: bool | None = None) -> list[GroupShape]:
    """Selected masked groups; `clip` True for clipping masks only, False for opacity masks only."""
    return [
        shape
        for shape in queries.selected_shapes(state)
        if isinstance(shape, GroupShape)
        and shape.masking is not None
        and (clip is None or (shape.masking.type == "clip") == clip)
    ]


def _make_refusal(state: AppState) -> str | None:
    """Why the selection can't be made a mask, or None."""
    if containers.edited_composite(state) is not None:
        return _("Masks can't be made inside a Composite")
    targets = queries.selected_shapes(state)
    if len(targets) < 2:
        return _("Select the objects to mask and, on top of them, the mask object")
    ids = {shape.id for shape in targets}
    if not any(ids <= {shape.id for shape in shapes} for shapes in containers.container_lists(state)):
        return _("The objects must be in the same layer or group")
    return None


def _can_make(session: Session) -> bool:
    return _make_refusal(session.state) is None


def _make(session: Session, mask_type: MaskType, label: str, message: str) -> None:
    """The top-most selected shape becomes the mask of the others; the new group takes its place."""
    state = session.state
    refusal = _make_refusal(state)
    if refusal is not None:
        state.status_message = refusal
        session.notify()
        return
    targets = queries.selected_shapes(state)
    target_ids = {shape.id for shape in targets}
    mask = targets[-1]
    with session.edit(label):
        masked = GroupShape(
            new_id(state), (*targets[:-1], mask), masking=Masking(mask_type, (mask.id,)), locked=False, hidden=False
        )

        def replace_targets(shapes: list[Shape]) -> list[Shape]:
            return [
                masked if shape.id == mask.id else shape
                for shape in shapes
                if shape.id == mask.id or shape.id not in target_ids
            ]

        containers.change_container(state, replace_targets)
        state.selection = {masked.id}
        state.status_message = message


def _release(session: Session, clip: bool, label: str, message: str) -> None:
    state = session.state
    groups = {group.id: group for group in _selected_masked(state, clip)}
    if not groups:
        return
    with session.edit(label):
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
        state.selection = {child.id for children in released.values() for child in children if not child.hidden}
        prune_selection(state)
        state.status_message = message


def _has_clip(session: Session) -> bool:
    return bool(_selected_masked(session.state, clip=True))


def _has_opacity_mask(session: Session) -> bool:
    return bool(_selected_masked(session.state, clip=False))


def _has_mask(session: Session) -> bool:
    return bool(_selected_masked(session.state))


def _top_is_image(state: AppState) -> bool:
    targets = queries.selected_shapes(state)
    return bool(targets) and isinstance(targets[-1], ImageShape)


def _can_make_clip(session: Session) -> bool:
    return _can_make(session) and not _top_is_image(session.state)


@operation("object.clip.make", N_("&Make Clipping Mask"), can_run=_can_make_clip)
def make_clip(session: Session) -> None:
    if _top_is_image(session.state):
        session.state.status_message = _("An image cannot be a clipping path")
        session.notify()
        return
    _make(session, "clip", _("Make Clipping Mask"), _("Made a clipping mask (double-click to edit it)"))


@operation("object.clip.release", N_("&Release Clipping Mask"), can_run=_has_clip)
def release_clip(session: Session) -> None:
    _release(session, True, _("Release Clipping Mask"), _("Released the clipping mask"))


@operation("object.mask.make", N_("Make &Opacity Mask"), can_run=_can_make)
def make_opacity_mask(session: Session) -> None:
    _make(session, "luminance", _("Make Opacity Mask"), _("Made an opacity mask (double-click to edit it)"))


@operation("object.mask.release", N_("Release O&pacity Mask"), can_run=_has_opacity_mask)
def release_opacity_mask(session: Session) -> None:
    _release(session, False, _("Release Opacity Mask"), _("Released the opacity mask"))


# --- changing a mask ----------------------------------------------------------------------------


def _change_groups(session: Session, groups: list[GroupShape], label: str, change) -> None:
    """Applies `change(masking)` to the masking of `groups`, wherever they are nested; one undo step."""
    wanted = {group.id for group in groups}
    state = session.state
    with session.edit(label):

        def apply(shape: Shape) -> Shape:
            if isinstance(shape, GroupShape) and shape.id in wanted and shape.masking is not None:
                return replace(shape, masking=change(shape.masking))
            return shape

        containers.map_shapes(state, apply)


def _all_inverted(session: Session) -> bool:
    groups = _selected_masked(session.state)
    return bool(groups) and all(group.masking.inverted for group in groups)


@operation("object.mask.invert", N_("&Invert Mask"), can_run=_has_mask, checked=_all_inverted)
def invert_mask(session: Session) -> None:
    groups = _selected_masked(session.state)
    if groups:
        flip = not all(group.masking.inverted for group in groups)
        _change_groups(session, groups, _("Invert Mask"), lambda masking: replace(masking, inverted=flip))


def _set_type(session: Session, mask_type: MaskType, label: str) -> None:
    groups = [group for group in _selected_masked(session.state, clip=False) if group.masking.type != mask_type]
    if groups:
        _change_groups(session, groups, label, lambda masking: replace(masking, type=mask_type))


def _is_type(mask_type: MaskType):
    def check(session: Session) -> bool:
        groups = _selected_masked(session.state, clip=False)
        return bool(groups) and all(group.masking.type == mask_type for group in groups)

    return check


@operation(
    "object.mask.type_luminance", N_("Mask by &Luminance"), can_run=_has_opacity_mask, checked=_is_type("luminance")
)
def mask_type_luminance(session: Session) -> None:
    _set_type(session, "luminance", _("Mask by Luminance"))


@operation("object.mask.type_alpha", N_("Mask by &Alpha"), can_run=_has_opacity_mask, checked=_is_type("alpha"))
def mask_type_alpha(session: Session) -> None:
    _set_type(session, "alpha", _("Mask by Alpha"))


# --- moving shapes between the mask and the content of an entered mask ---------------------------


def _entered_mask(state: AppState) -> GroupShape | None:
    container = containers.edited_container(state)
    if isinstance(container, GroupShape) and container.masking is not None:
        return container
    return None


def _selected_children(state: AppState, to_mask: bool) -> list[Shape]:
    group = _entered_mask(state)
    if group is None:
        return []
    return [shape for shape in queries.selected_shapes(state) if group.masking.is_mask(shape.id) != to_mask]


def _can_move_to_mask(session: Session) -> bool:
    return bool(_selected_children(session.state, True))


def _can_move_to_content(session: Session) -> bool:
    return bool(_selected_children(session.state, False))


def _move(session: Session, to_mask: bool, label: str) -> None:
    state = session.state
    moving = {shape.id for shape in _selected_children(state, to_mask)}
    group = _entered_mask(state)
    if not moving or group is None:
        return
    mask_ids = tuple(shape.id for shape in group.children if group.masking.is_mask(shape.id) != (shape.id in moving))
    _change_groups(session, [group], label, lambda masking: replace(masking, mask_ids=mask_ids))
    count = len(moving)
    state.status_message = (
        ngettext("Moved {count} object to the mask", "Moved {count} objects to the mask", count)
        if to_mask
        else ngettext("Moved {count} object to the content", "Moved {count} objects to the content", count)
    ).format(count=count)


@operation("object.mask.to_mask", N_("Add to Mas&k"), can_run=_can_move_to_mask)
def move_to_mask(session: Session) -> None:
    _move(session, True, _("Add to Mask"))


@operation("object.mask.to_content", N_("Mov&e to Content"), can_run=_can_move_to_content)
def move_to_content(session: Session) -> None:
    _move(session, False, _("Move to Content"))
