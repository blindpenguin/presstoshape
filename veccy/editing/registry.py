"""Table of operations that menus, toolbars and shortcuts can run without extra input.

Filled at import time by the operation modules (`@operation` / `register`); it holds definitions, no app state.
"""

from collections.abc import Callable
from dataclasses import dataclass

from veccy.editing.session import Session

Check = Callable[[Session], bool]


def _always(session: Session) -> bool:
    return True


@dataclass(frozen=True)
class Operation:
    # Stable dotted id ("edit.delete"), used by the keymap and menu layouts.
    id: str
    # Menu text, with its mnemonic ("&Delete").
    label: str
    run: Callable[[Session], None]
    can_run: Check = _always

    def invoke(self, session: Session) -> None:
        if self.can_run(session):
            self.run(session)


_OPERATIONS: dict[str, Operation] = {}


def register(id: str, label: str, run: Callable[[Session], None], can_run: Check | None = None) -> Operation:
    if id in _OPERATIONS:
        raise ValueError(f"operation {id!r} is already registered")
    entry = Operation(id, label, run, can_run or _always)
    _OPERATIONS[id] = entry
    return entry


def operation(id: str, label: str, can_run: Check | None = None):
    """Registers `fn(session)` and returns it unchanged, so it stays a plain function to call."""

    def decorate(fn: Callable[[Session], None]) -> Callable[[Session], None]:
        register(id, label, fn, can_run)
        return fn

    return decorate


def operations() -> list[Operation]:
    """In registration order."""
    return list(_OPERATIONS.values())


def find(id: str) -> Operation:
    return _OPERATIONS[id]
