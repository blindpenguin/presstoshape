"""The one AppState of a running app, its undo history and change notification. Operations edit through `edit()`."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from veccy.models.app_state import AppState, Document, Layer

_UNDO_LIMIT = 200


@dataclass
class _Snapshot:
    document: Document
    selected_layer_index: int


@dataclass
class _Step:
    snapshot: _Snapshot
    label: str


def _copy_document(doc: Document) -> Document:
    # Shapes are frozen, so copying the layer lists is enough to isolate a snapshot.
    layers = [Layer(layer.name, layer.visible, list(layer.shapes)) for layer in doc.layers]
    return Document(doc.width, doc.height, layers, doc.next_id)


class Session:
    def __init__(self, state: AppState | None = None) -> None:
        self.state = state if state is not None else AppState()
        self._undo: list[_Step] = []
        self._redo: list[_Step] = []
        self._merge_key: str | None = None
        self._listeners: list[Callable[[], None]] = []

    # --- notification -------------------------------------------------------

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    # --- editing ------------------------------------------------------------

    @contextmanager
    def edit(self, label: str, merge_key: str | None = None) -> Iterator[AppState]:
        """One undoable step named `label`: snapshot first, mark dirty and notify once the body is done.

        Consecutive edits with the same `merge_key` extend the previous step (spinbox steps, rotation field).
        If the body raises, the document is restored, nothing is recorded and nobody is notified.
        """
        before = self._snapshot()
        try:
            yield self.state
        except BaseException:
            self._apply(before)
            raise
        self._record(before, label, merge_key)
        self.notify()

    def _record(self, before: _Snapshot, label: str, merge_key: str | None) -> None:
        if merge_key is None or merge_key != self._merge_key:
            self._undo.append(_Step(before, label))
            del self._undo[:-_UNDO_LIMIT]
        self._merge_key = merge_key
        self._redo.clear()
        self.state.dirty = True

    def end_merge(self) -> None:
        """The next edit starts a new undo step even if its merge key matches (e.g. after a selection change)."""
        self._merge_key = None

    def clear_history(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._merge_key = None

    # --- undo / redo --------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def undo_count(self) -> int:
        return len(self._undo)

    @property
    def undo_label(self) -> str | None:
        return self._undo[-1].label if self._undo else None

    @property
    def redo_label(self) -> str | None:
        return self._redo[-1].label if self._redo else None

    def undo(self) -> None:
        if self._undo:
            self._step(self._undo, self._redo, "Undo")

    def redo(self) -> None:
        if self._redo:
            self._step(self._redo, self._undo, "Redo")

    def _step(self, source: list[_Step], target: list[_Step], message: str) -> None:
        step = source.pop()
        target.append(_Step(self._snapshot(), step.label))
        self._apply(step.snapshot)
        self._merge_key = None
        state = self.state
        state.dirty = True
        visible = {shape.id for layer in state.document.layers if layer.visible for shape in layer.shapes}
        state.selection &= visible
        state.node_selection = frozenset()
        state.status_message = message
        self.notify()

    def _snapshot(self) -> _Snapshot:
        return _Snapshot(_copy_document(self.state.document), self.state.selected_layer_index)

    def _apply(self, snapshot: _Snapshot) -> None:
        self.state.document = snapshot.document
        self.state.selected_layer_index = min(snapshot.selected_layer_index, len(snapshot.document.layers) - 1)
