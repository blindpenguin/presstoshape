from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QToolButton, QWidget

from presstoshape.editing import containers
from presstoshape.editing.operations import composites
from presstoshape.editing.session import Session
from presstoshape.models.app_state import AppState


class EditBar(QWidget):
    """Shown above the canvas while a Composite is edited: where you are, a way back to any level, and Done."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._path: tuple[int, ...] | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.addWidget(QLabel("Editing:"))
        self._crumbs = QHBoxLayout()
        self._crumbs.setSpacing(2)
        layout.addLayout(self._crumbs)
        layout.addStretch(1)
        done = QPushButton("Done")
        done.setToolTip("Leave this Composite (Esc)")
        done.clicked.connect(lambda: composites.leave(session))
        layout.addWidget(done)
        self.setVisible(False)

    def refresh(self, state: AppState) -> None:
        path = containers.valid_edit_path(state)
        self.setVisible(bool(path))
        if path == self._path:
            return
        self._path = path
        while self._crumbs.count():
            item = self._crumbs.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not path:
            return
        layer_name = next(
            (layer.name for layer in state.document.layers if any(shape.id == path[0] for shape in layer.shapes)), ""
        )
        names = [layer_name] + ["Composite"] * len(path)
        for depth, name in enumerate(names):
            if depth:
                self._crumbs.addWidget(QLabel("›"))
            button = QToolButton()
            button.setText(name)
            button.setAutoRaise(True)
            levels = len(path) - depth
            if levels:
                button.clicked.connect(lambda _checked=False, count=levels: self._leave(count))
            else:
                button.setEnabled(False)
            self._crumbs.addWidget(button)

    def _leave(self, levels: int) -> None:
        composites.leave(self._session, levels)
