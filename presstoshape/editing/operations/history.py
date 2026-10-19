"""Undo and redo as registered commands."""

from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.i18n import N_


@operation("edit.undo", N_("&Undo"), can_run=lambda session: session.can_undo)
def undo(session: Session) -> None:
    session.undo()


@operation("edit.redo", N_("&Redo"), can_run=lambda session: session.can_redo)
def redo(session: Session) -> None:
    session.redo()
