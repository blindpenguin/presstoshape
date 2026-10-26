"""Swatches in the document's palette (undoable, saved with the file) and in the personal library (app-wide, not
undoable). Every operation takes the palette it works on."""

from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Literal

from presstoshape.editing import queries
from presstoshape.editing.operations._document import new_id
from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.colours import Swatch
from presstoshape.models.shapes import Style, sanitized

Palette = Literal["document", "library"]

# (name, colour, opacity)
SwatchValues = tuple[str, str, float]


def palette_swatches(session: Session, palette: Palette) -> tuple[Swatch, ...]:
    state = session.state
    return state.document.swatches if palette == "document" else state.colours.library


def _opacity(value: float) -> float:
    return sanitized(Style(opacity=value)).opacity


def _change(
    session: Session,
    palette: Palette,
    label: str,
    change: Callable[[tuple[Swatch, ...], Callable[[], int]], tuple[Swatch, ...]],
) -> None:
    """Replaces the palette with `change(swatches, next_id)`; a document change is one undo step."""
    state = session.state
    if palette == "document":
        before = state.document.swatches
        if change(before, lambda: 0) == before:
            return
        with session.edit(label):
            state.document.swatches = change(state.document.swatches, lambda: new_id(state))
        return
    library = state.colours.library
    counter = iter(range(max((swatch.id for swatch in library), default=0) + 1, 1 << 62))
    changed = change(library, lambda: next(counter))
    if changed != library:
        state.colours.library = changed
        session.notify()


def _has(swatches: Iterable[Swatch], color: str, opacity: float) -> bool:
    return any(swatch.color == color and swatch.opacity == opacity for swatch in swatches)


def add_swatch(session: Session, palette: Palette, color: str, opacity: float = 1.0, name: str = "") -> None:
    color, opacity = color.lower(), _opacity(opacity)
    _change(session, palette, _("Add swatch"), lambda swatches, ids: (*swatches, Swatch(ids(), name, color, opacity)))


def _map_one(session: Session, palette: Palette, label: str, swatch_id: int, change: Callable[[Swatch], Swatch]):
    _change(
        session,
        palette,
        label,
        lambda swatches, ids: tuple(change(swatch) if swatch.id == swatch_id else swatch for swatch in swatches),
    )


def rename_swatch(session: Session, palette: Palette, swatch_id: int, name: str) -> None:
    _map_one(session, palette, _("Rename swatch"), swatch_id, lambda swatch: replace(swatch, name=name.strip()))


def replace_swatch(session: Session, palette: Palette, swatch_id: int, color: str, opacity: float = 1.0) -> None:
    color, opacity = color.lower(), _opacity(opacity)
    _map_one(
        session, palette, _("Replace swatch"), swatch_id, lambda swatch: replace(swatch, color=color, opacity=opacity)
    )


def delete_swatch(session: Session, palette: Palette, swatch_id: int) -> None:
    _change(
        session,
        palette,
        _("Delete swatch"),
        lambda swatches, ids: tuple(swatch for swatch in swatches if swatch.id != swatch_id),
    )


def delete_all_swatches(session: Session, palette: Palette) -> None:
    _change(session, palette, _("Delete all swatches"), lambda swatches, ids: ())


def move_swatch(session: Session, palette: Palette, swatch_id: int, step: int) -> None:
    """Moves the swatch `step` places (negative: towards the start), stopping at the ends."""

    def moved(swatches: tuple[Swatch, ...], ids: Callable[[], int]) -> tuple[Swatch, ...]:
        order = list(swatches)
        index = next((i for i, swatch in enumerate(order) if swatch.id == swatch_id), None)
        if index is None:
            return swatches
        target = min(len(order) - 1, max(0, index + step))
        order.insert(target, order.pop(index))
        return tuple(order)

    _change(session, palette, _("Move swatch"), moved)


def import_swatches(session: Session, palette: Palette, values: Iterable[SwatchValues], label: str = "") -> int:
    """Adds each (name, colour, opacity) not in the palette yet; the number added."""
    values = [(name, color.lower(), _opacity(opacity)) for name, color, opacity in values]

    def added(swatches: tuple[Swatch, ...], ids: Callable[[], int]) -> tuple[Swatch, ...]:
        result = list(swatches)
        for name, color, opacity in values:
            if not _has(result, color, opacity):
                result.append(Swatch(ids(), name, color, opacity))
        return tuple(result)

    before = len(palette_swatches(session, palette))
    _change(session, palette, label or _("Import palette"), added)
    return len(palette_swatches(session, palette)) - before


def copy_swatch(session: Session, source: Palette, swatch_id: int) -> None:
    """Copies a swatch into the other palette, unless that one has its colour already."""
    swatch = next((s for s in palette_swatches(session, source) if s.id == swatch_id), None)
    if swatch is not None:
        target: Palette = "library" if source == "document" else "document"
        import_swatches(session, target, [(swatch.name, swatch.color, swatch.opacity)], _("Add swatch"))


def add_document_colours(session: Session) -> int:
    """Every colour the visible drawing uses becomes a document swatch; the number added."""
    colors = queries.document_colours(session.state.document)
    return import_swatches(session, "document", [("", color, 1.0) for color in colors], _("Add document colours"))
