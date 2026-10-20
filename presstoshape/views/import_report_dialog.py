"""Lists what an opened file lost on import, so nobody saves over it without noticing."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout, QWidget

from presstoshape.i18n import _


class ImportReportDialog(QDialog):
    def __init__(self, file_name: str, notes: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Import Notes"))
        heading = QLabel(_("Some parts of {name} couldn't be imported as they are:").format(name=file_name))
        heading.setWordWrap(True)
        self.notes = QListWidget()
        self.notes.addItems(notes)
        self.notes.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.notes.setWordWrap(True)
        self.notes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.notes.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.notes.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hint = QLabel(
            _(
                "Saving as SVG writes the file without these parts. Save as a PressToShape file (.p2s) or under "
                "a new name to keep the original."
            )
        )
        hint.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self.notes, 1)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.resize(480, 320)
