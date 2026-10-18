"""Undo and redo as registered commands."""

from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session


@operation("edit.undo", "&Undo", can_run=lambda session: session.can_undo)
def undo(session: Session) -> None:
    session.undo()


@operation("edit.redo", "&Redo", can_run=lambda session: session.can_redo)
def redo(session: Session) -> None:
    session.redo()
