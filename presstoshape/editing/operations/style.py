"""Fill, stroke and stroke width of the selected shapes. Tool defaults live in view.set_tool_style."""

from dataclasses import replace

from presstoshape.editing.operations._document import map_selected
from presstoshape.editing.session import Session


def set_fill(session: Session, color: str | None) -> None:
    _restyle(session, "Change fill", fill=color)


def set_stroke(session: Session, color: str | None) -> None:
    _restyle(session, "Change stroke", stroke=color)


def set_stroke_width(session: Session, width: float) -> None:
    _restyle(session, "Change stroke width", merge_key="stroke_width", stroke_width=max(0.0, width))


def _restyle(session: Session, label: str, merge_key: str | None = None, **changes) -> None:
    if not session.state.selection:
        return
    with session.edit(label, merge_key):
        map_selected(session.state, lambda shape: replace(shape, style=replace(shape.style, **changes)))
