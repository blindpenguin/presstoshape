from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget

from presstoshape.models.app_state import Document
from presstoshape.render.export import MAX_SIDE, export_size

_MIN_SCALE = 0.1


class ExportPngDialog(QDialog):
    """Asks for the export scale, showing the resulting pixel size."""

    def __init__(self, doc: Document, scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export PNG")
        self._doc = doc
        self._scale = QDoubleSpinBox()
        self._scale.setDecimals(2)
        self._scale.setSingleStep(0.5)
        self._scale.setRange(_MIN_SCALE, max(_MIN_SCALE, MAX_SIDE / max(doc.width, doc.height, 1)))
        self._scale.setSuffix(" ×")
        self._size = QLabel()
        self._scale.valueChanged.connect(lambda: self._update_size())
        self._scale.setValue(scale)
        self._update_size()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("Scale", self._scale)
        form.addRow("Size", self._size)
        form.addRow(buttons)

    def _update_size(self) -> None:
        width, height = export_size(self._doc, self._scale.value())
        self._size.setText(f"{width} × {height} px")

    @classmethod
    def ask(cls, doc: Document, scale: float, parent: QWidget | None = None) -> float | None:
        dialog = cls(doc, scale, parent)
        return dialog._scale.value() if dialog.exec() == QDialog.DialogCode.Accepted else None
