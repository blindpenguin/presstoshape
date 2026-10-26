"""The stored palettes (the library): named swatch collections kept in the app's data folder. App-level state like
recent colours: changes notify, they are not undo steps."""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.models.colours import Palette, Swatch
from presstoshape.models.shapes import Style, sanitized

_NUMBERED = re.compile(r"^(.*?) \((\d+)\)$")


def find_palette(state: AppState, palette_id: int | None) -> Palette | None:
    return next((palette for palette in state.colours.palettes if palette.id == palette_id), None)


def current_palette(state: AppState) -> Palette | None:
    return find_palette(state, state.colours.current_palette)


def unique_name(palettes: Iterable[Palette], name: str, ignore_id: int | None = None) -> str:
    """`name` trimmed (empty: "Palette"), numbered "Name (2)", "Name (3)", … when another palette has it; names
    compare without case, as file systems may."""
    name = " ".join(name.split()) or _("Palette")
    taken = {palette.name.casefold() for palette in palettes if palette.id != ignore_id}
    if name.casefold() not in taken:
        return name
    match = _NUMBERED.match(name)
    base, number = (match.group(1), int(match.group(2))) if match else (name, 1)
    while True:
        number += 1
        candidate = f"{base} ({number})"
        if candidate.casefold() not in taken:
            return candidate


def _next_id(state: AppState) -> int:
    return max((palette.id for palette in state.colours.palettes), default=0) + 1


def _set(session: Session, palettes: Sequence[Palette], current: int | None) -> None:
    colours = session.state.colours
    colours.palettes = tuple(palettes)
    ids = {palette.id for palette in colours.palettes}
    colours.current_palette = current if current in ids else (colours.palettes[0].id if colours.palettes else None)
    session.notify()


def set_palettes(session: Session, palettes: Sequence[Palette], current_name: str | None = None) -> None:
    """The palettes loaded from disk; `current_name` picks the current one (the first if it is gone)."""
    current = next((palette.id for palette in palettes if palette.name == current_name), None)
    _set(session, palettes, current)


def new_palette(session: Session, name: str, swatches: tuple = ()) -> int:
    """Adds an empty (or given) palette at the end and makes it current."""
    state = session.state
    palette = Palette(_next_id(state), unique_name(state.colours.palettes, name), tuple(swatches))
    _set(session, (*state.colours.palettes, palette), palette.id)
    return palette.id


def rename_palette(session: Session, palette_id: int, name: str) -> bool:
    """False (nothing changed) for an empty name or one another palette has; notifies either way, so the view
    shows the name the palette has."""
    colours = session.state.colours
    name = " ".join(name.split())
    taken = {palette.name.casefold() for palette in colours.palettes if palette.id != palette_id}
    if not name or name.casefold() in taken:
        session.notify()
        return False
    _set(
        session,
        [replace(p, name=name) if p.id == palette_id else p for p in colours.palettes],
        colours.current_palette,
    )
    return True


def duplicate_palette(session: Session, palette_id: int) -> int | None:
    """A copy right after the original, named "<name> copy", made current."""
    state = session.state
    source = find_palette(state, palette_id)
    if source is None:
        return None
    copy = Palette(
        _next_id(state), unique_name(state.colours.palettes, _("{name} copy").format(name=source.name)), source.swatches
    )
    palettes = list(state.colours.palettes)
    palettes.insert(palettes.index(source) + 1, copy)
    _set(session, palettes, copy.id)
    return copy.id


def delete_palettes(session: Session, palette_ids: Iterable[int]) -> None:
    """Removes the palettes; if the current one goes, the next remaining one (else the previous) becomes current."""
    colours = session.state.colours
    gone = set(palette_ids)
    order = list(colours.palettes)
    kept = [palette for palette in order if palette.id not in gone]
    current = colours.current_palette
    if current in gone:
        index = next(i for i, palette in enumerate(order) if palette.id == current)
        after = [palette for palette in order[index:] if palette.id not in gone]
        before = [palette for palette in order[:index] if palette.id not in gone]
        current = after[0].id if after else before[-1].id if before else None
    _set(session, kept, current)


def set_palette_order(session: Session, palette_ids: Sequence[int]) -> None:
    """The palettes in this order (from a drag in the Settings list); unknown ids are ignored, missing ones keep
    their relative order at the end."""
    colours = session.state.colours
    by_id = {palette.id: palette for palette in colours.palettes}
    ordered = [by_id[palette_id] for palette_id in dict.fromkeys(palette_ids) if palette_id in by_id]
    ordered += [palette for palette in colours.palettes if palette not in ordered]
    if tuple(ordered) != colours.palettes:
        _set(session, ordered, colours.current_palette)


def set_current_palette(session: Session, palette_id: int) -> None:
    if find_palette(session.state, palette_id) is not None:
        session.state.colours.current_palette = palette_id
        session.notify()


def replace_palette(session: Session, palette: Palette) -> None:
    """The palette with the same id takes `palette`'s place (its swatches changed)."""
    colours = session.state.colours
    _set(session, [palette if p.id == palette.id else p for p in colours.palettes], colours.current_palette)


# A file's palette as read: its name and (name, "#rrggbb", opacity) colours.
@dataclass(frozen=True)
class ImportItem:
    name: str
    colors: tuple[tuple[str, str, float], ...]


Choice = Literal["keep", "replace", "skip"]


@dataclass(frozen=True)
class ImportCounts:
    imported: int = 0
    replaced: int = 0
    skipped: int = 0


def clashes(palettes: Sequence[Palette], items: Sequence[ImportItem]) -> list[int]:
    """Indices of the items whose name (without case) an existing palette or an earlier item already has."""
    taken = {palette.name.casefold() for palette in palettes}
    found = []
    for index, item in enumerate(items):
        key = item.name.casefold()
        if key in taken:
            found.append(index)
        taken.add(key)
    return found


def _swatches(colors: Iterable[tuple[str, str, float]]) -> tuple[Swatch, ...]:
    return tuple(
        Swatch(number, name, color.lower(), sanitized(Style(opacity=opacity)).opacity)
        for number, (name, color, opacity) in enumerate(colors, 1)
    )


def apply_import(session: Session, items: Sequence[ImportItem], choices: Mapping[int, Choice]) -> ImportCounts:
    """Adds each item as a palette at the end, in order. A clashing item does what `choices` says (default
    "keep"): "keep" numbers its name, "replace" gives the palette that has the name at that point (existing, or
    imported earlier in this batch) the item's swatches, keeping its place, "skip" leaves it out. The first new
    palette becomes current when there was none. One notify."""
    state = session.state
    palettes = list(state.colours.palettes)
    next_id = _next_id(state)
    imported = replaced = skipped = 0
    first_new: int | None = None
    for index, item in enumerate(items):
        holder = next((i for i, p in enumerate(palettes) if p.name.casefold() == item.name.casefold()), None)
        choice = choices.get(index, "keep") if holder is not None else "keep"
        if choice == "skip":
            skipped += 1
        elif choice == "replace" and holder is not None:
            palettes[holder] = replace(palettes[holder], swatches=_swatches(item.colors))
            replaced += 1
        else:
            palettes.append(Palette(next_id, unique_name(palettes, item.name), _swatches(item.colors)))
            first_new = next_id if first_new is None else first_new
            next_id += 1
            imported += 1
    current = state.colours.current_palette
    _set(session, palettes, current if current is not None else first_new)
    return ImportCounts(imported, replaced, skipped)
