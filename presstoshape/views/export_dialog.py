from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget

from presstoshape.i18n import _
from presstoshape.models.app_state import Document
from presstoshape.render.export import MAX_SIDE, export_size

_MIN_SCALE = 0.1


class ExportPngDialog(QDialog):
    """Asks for the export resolution as DPI or scale (linked), showing the resulting pixel size."""

    def __init__(self, doc: Document, scale: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Export PNG"))
        self._doc = doc
        max_scale = max(_MIN_SCALE, MAX_SIDE / max(doc.width, doc.height, 1))
        self._scale = QDoubleSpinBox()
        self._scale.setDecimals(2)
        self._scale.setSingleStep(0.5)
        self._scale.setRange(_MIN_SCALE, max_scale)
        self._scale.setSuffix(" ×")
        self._dpi = QDoubleSpinBox()
        self._dpi.setDecimals(1)
        self._dpi.setSingleStep(12)
        self._dpi.setRange(_MIN_SCALE * doc.dpi, max_scale * doc.dpi)
        self._dpi.setSuffix(" dpi")
        self._size = QLabel()
        self._scale.valueChanged.connect(lambda: self._on_scale())
        self._dpi.valueChanged.connect(lambda: self._on_dpi())
        self._scale.setValue(scale)
        self._on_scale()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow(_("Resolution"), self._dpi)
        form.addRow(_("Scale"), self._scale)
        form.addRow(_("Size"), self._size)
        form.addRow(buttons)

    def _on_scale(self) -> None:
        self._dpi.blockSignals(True)
        self._dpi.setValue(self._scale.value() * self._doc.dpi)
        self._dpi.blockSignals(False)
        self._update_size()

    def _on_dpi(self) -> None:
        self._scale.blockSignals(True)
        self._scale.setValue(self._dpi.value() / self._doc.dpi)
        self._scale.blockSignals(False)
        self._update_size()

    def _update_size(self) -> None:
        width, height = export_size(self._doc, self._dpi.value() / self._doc.dpi)
        self._size.setText(_("{width} × {height} px").format(width=width, height=height))

    @property
    def scale(self) -> float:
        # From the DPI field: the scale field rounds to 2 decimals, the DPI to 1.
        return self._dpi.value() / self._doc.dpi

    @classmethod
    def ask(cls, doc: Document, scale: float, parent: QWidget | None = None) -> float | None:
        dialog = cls(doc, scale, parent)
        return dialog.scale if dialog.exec() == QDialog.DialogCode.Accepted else None
