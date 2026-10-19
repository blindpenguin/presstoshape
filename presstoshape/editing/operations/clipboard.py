"""Copy, cut, paste and duplicate. The system clipboard belongs to the views: these take and return plain data."""

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import add_on_top, delete_selected, insert_copies, with_fresh_ids
from presstoshape.editing.operations.paths import to_path
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.formats.clipboard import ClipboardError, decode_shapes, encode_shapes
from presstoshape.formats.svg import read_shapes_svg, write_shapes_svg
from presstoshape.geometry import transforms
from presstoshape.geometry.boxes import Point, Rect
from presstoshape.models.shapes import PartMode, Shape, TextShape
from presstoshape.render.paths import PathCache


@dataclass(frozen=True)
class ClipboardContent:
    native: bytes
    svg: str


def _has_selection(session: Session) -> bool:
    return bool(session.state.selection)


def _bounds(shapes: Sequence[Shape]) -> Rect:
    """Visual bounds (strokes included) of all `shapes`; at least one unit wide and high, so an SVG viewBox
    stays valid for a lone horizontal line."""
    cache = PathCache()
    # By hand: skia.Rect.join skips zero-height or zero-width rects.
    rects = [cache.bounds(shape) for shape in shapes]
    left, top = min(rect.left() for rect in rects), min(rect.top() for rect in rects)
    right, bottom = max(rect.right() for rect in rects), max(rect.bottom() for rect in rects)
    return left, top, max(right - left, 1.0), max(bottom - top, 1.0)


def _content(shapes: Sequence[Shape]) -> ClipboardContent:
    return ClipboardContent(encode_shapes(shapes), write_shapes_svg(shapes, _bounds(shapes)))


def copy_selection(session: Session) -> ClipboardContent | None:
    """The selected shapes (whole shapes, also under the Node tool) for the clipboard; changes no document."""
    state = session.state
    shapes = queries.selected_shapes(state)
    if not shapes:
        return None
    state.status_message = f"Copied {len(shapes)} object(s)"
    session.notify()
    return _content(shapes)


def cut_selection(session: Session) -> ClipboardContent | None:
    state = session.state
    shapes = queries.selected_shapes(state)
    if not shapes:
        return None
    content = _content(shapes)
    with session.edit("Cut"):
        delete_selected(state)
        state.node_selection = frozenset()
        state.status_message = f"Cut {len(shapes)} object(s)"
    return content


def _decode(native: bytes | None, svg: str | None) -> tuple[list[Shape], list[str]] | str:
    """Shapes from the native data, else from the SVG; a reason for the status bar if neither works."""
    if native is not None:
        try:
            return decode_shapes(native), []
        except ClipboardError:
            pass
    if svg is None:
        return "Nothing to paste"
    try:
        shapes, notes = read_shapes_svg(svg)
    except (ET.ParseError, ValueError):
        return "Nothing to paste: the clipboard's SVG couldn't be read"
    return (shapes, notes) if shapes else "Nothing to paste: " + ("; ".join(notes) or "the SVG holds no shapes")


def paste(session: Session, native: bytes | None, svg: str | None, center: Point | None) -> bool:
    """Adds the clipboard shapes on top of the active container and selects them. With `center` they are centered
    there (Paste), without it they keep their coordinates (Paste in Place)."""
    state = session.state
    decoded = _decode(native, svg)
    if isinstance(decoded, str):
        state.status_message = decoded
        session.notify()
        return False
    shapes, notes = decoded
    in_composite = containers.editing(state)
    if in_composite and any(isinstance(shape, TextShape) for shape in shapes):
        shapes = [to_path(shape) if isinstance(shape, TextShape) else shape for shape in shapes]
        notes = [*notes, "text became a path inside the Composite"]
    if center is not None:
        x, y, width, height = _bounds(shapes)
        dx, dy = center[0] - (x + width / 2), center[1] - (y + height / 2)
        shapes = [transforms.translate(shape, dx, dy) for shape in shapes]
    layer = queries.active_layer(state)
    if not in_composite and not layer.visible:
        notes = [*notes, f"layer '{layer.name}' is hidden"]
    with session.edit("Paste" if center is not None else "Paste in Place"):
        pasted = with_fresh_ids(state, shapes)
        add_on_top(state, pasted)
        state.selection = {shape.id for shape in pasted}
        state.node_selection = frozenset()
        state.status_message = f"Pasted {len(pasted)} object(s)" + "".join(f"; {note}" for note in notes)
    return True


def _duplicate(session: Session, dx: float = 0.0, dy: float = 0.0) -> None:
    state = session.state
    originals = queries.selected_shapes(state)
    if not originals:
        return
    with session.edit("Duplicate"):
        moved = [transforms.translate(shape, dx, dy) for shape in originals] if (dx, dy) != (0, 0) else originals
        copies = with_fresh_ids(state, moved)
        modes: dict[int, PartMode] = {}
        for original, copy in zip(originals, copies):
            mode = containers.part_mode(state, original.id)
            if mode is not None:
                modes[copy.id] = mode
        insert_copies(state, {original.id: copy for original, copy in zip(originals, copies)}, modes)
        state.selection = {shape.id for shape in copies}
        state.node_selection = frozenset()
        state.status_message = f"Duplicated {len(copies)} object(s)"


@operation("edit.duplicate", "D&uplicate", can_run=_has_selection)
def duplicate_selection(session: Session) -> None:
    """Copies of the selection in place, directly above the originals; the clipboard is left alone."""
    _duplicate(session)


def duplicate_and_move(session: Session, dx: float, dy: float) -> None:
    """Alt+drag: the copies land moved by (dx, dy); one undo step."""
    _duplicate(session, dx, dy)
