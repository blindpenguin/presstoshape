"""Exact position of one guide, typed in the document's unit; also deletes it."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QPushButton, QWidget

from presstoshape.i18n import _
from presstoshape.models.app_state import Unit
from presstoshape.models.layout import Guide
from presstoshape.views.unit_fields import LengthSpinBox

_RANGE_PX = 100_000.0


class GuideDialog(QDialog):
    """After exec(): `deleted`, or the new `position` in document px when accepted."""

    def __init__(self, guide: Guide, unit: Unit, dpi: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Guide"))
        self.deleted = False
        self.position = guide.position
        layout = QFormLayout(self)
        if guide.orientation == "horizontal":
            explanation = _("Horizontal guide, measured from the top of the artboard")
            label = _("Y")
        else:
            explanation = _("Vertical guide, measured from the left of the artboard")
            label = _("X")
        layout.addRow(QLabel(explanation))
        self._position = LengthSpinBox(-_RANGE_PX, _RANGE_PX)
        self._position.set_unit(unit, dpi)
        self._position.set_px(guide.position)
        layout.addRow(label, self._position)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        delete = QPushButton(_("Delete Guide"))
        buttons.addButton(delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        delete.clicked.connect(lambda: self._delete())
        buttons.accepted.connect(lambda: self._accept())
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _accept(self) -> None:
        self.position = self._position.px()
        self.accept()

    def _delete(self) -> None:
        self.deleted = True
        self.accept()
