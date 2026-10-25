"""Exact kind and radius for live corners (double-click a corner widget)."""

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QWidget

from presstoshape.i18n import _, pgettext
from presstoshape.models.app_state import Unit
from presstoshape.models.shapes import CORNER_KINDS, CornerKind
from presstoshape.views.unit_fields import LengthSpinBox

_MAX_RADIUS_PX = 100_000.0


def kind_labels() -> dict[CornerKind, str]:
    return {
        "round": pgettext("corner", "Round"),
        "inverted": pgettext("corner", "Inverted"),
        "chamfer": pgettext("corner", "Chamfer"),
    }


def kind_box() -> QComboBox:
    box = QComboBox()
    for kind, label in kind_labels().items():
        box.addItem(label, kind)
    return box


class CornerDialog(QDialog):
    """After exec() and OK: `kind` and `radius` (document px)."""

    def __init__(self, kind: CornerKind, radius: float, unit: Unit, dpi: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Corner"))
        self.kind: CornerKind = kind
        self.radius = radius
        layout = QFormLayout(self)
        self._kind = kind_box()
        self._kind.setCurrentIndex(CORNER_KINDS.index(kind))
        layout.addRow(_("Kind"), self._kind)
        self._radius = LengthSpinBox(0.0, _MAX_RADIUS_PX)
        self._radius.set_unit(unit, dpi)
        self._radius.set_px(radius)
        layout.addRow(_("Radius"), self._radius)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(lambda: self._accept())
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _accept(self) -> None:
        self.kind = self._kind.currentData()
        self.radius = self._radius.px()
        self.accept()
