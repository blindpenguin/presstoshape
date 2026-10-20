"""Guides and the grid: document data, so every change is an undo step."""

from dataclasses import replace

from presstoshape.editing.operations._document import new_id
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.layout import GridSettings, Guide, GuideOrientation


def add_guide(session: Session, orientation: GuideOrientation, position: float) -> int:
    if orientation not in ("horizontal", "vertical"):
        raise ValueError(f"unknown guide orientation {orientation!r}")
    state = session.state
    with session.edit(_("Add guide")):
        guide = Guide(new_id(state), orientation, float(position))
        state.document.guides = (*state.document.guides, guide)
        state.status_message = _("Added a guide")
    return guide.id


def move_guide(session: Session, guide_id: int, position: float) -> None:
    """Consecutive moves of one guide form one undo step."""
    document = session.state.document
    guide = next((guide for guide in document.guides if guide.id == guide_id), None)
    if guide is None or guide.position == position:
        return
    with session.edit(_("Move guide"), merge_key=f"guide:{guide_id}"):
        moved = replace(guide, position=float(position))
        document.guides = tuple(moved if other.id == guide_id else other for other in document.guides)


def delete_guide(session: Session, guide_id: int) -> None:
    document = session.state.document
    if not any(guide.id == guide_id for guide in document.guides):
        return
    with session.edit(_("Delete guide")):
        document.guides = tuple(guide for guide in document.guides if guide.id != guide_id)
        session.state.status_message = _("Deleted a guide")


def _has_guides(session: Session) -> bool:
    return bool(session.state.document.guides)


@operation("view.clear_guides", N_("Cl&ear Guides"), can_run=_has_guides)
def clear_guides(session: Session) -> None:
    if not session.state.document.guides:
        return
    with session.edit(_("Clear guides")):
        session.state.document.guides = ()
        session.state.status_message = _("Cleared all guides")


def set_grid(session: Session, spacing: float, major_every: int) -> None:
    """Spacing in document px; refuses non-positive values."""
    if spacing <= 0 or major_every < 1:
        raise ValueError("grid spacing must be positive and major lines at least every line")
    grid = GridSettings(float(spacing), int(major_every))
    if session.state.document.grid == grid:
        return
    with session.edit(_("Change grid")):
        session.state.document.grid = grid
