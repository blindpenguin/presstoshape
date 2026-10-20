"""Grid spacing (in the document's unit) and how often a major line is drawn."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QWidget

from presstoshape.i18n import _
from presstoshape.models.app_state import Unit
from presstoshape.models.layout import GridSettings
from presstoshape.views.unit_fields import LengthSpinBox

_MIN_SPACING_PX = 0.01
_MAX_SPACING_PX = 10_000.0


class GridDialog(QDialog):
    """After an accepted exec(): `grid` with the new values (spacing in document px)."""

    def __init__(self, grid: GridSettings, unit: Unit, dpi: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Grid"))
        self.grid = grid
        layout = QFormLayout(self)
        self._spacing = LengthSpinBox(_MIN_SPACING_PX, _MAX_SPACING_PX, fine=True)
        self._spacing.set_unit(unit, dpi)
        self._spacing.set_px(grid.spacing)
        layout.addRow(_("Spacing"), self._spacing)
        self._major = QSpinBox()
        self._major.setRange(1, 100)
        self._major.setValue(grid.major_every)
        self._major.setToolTip(_("Every this many lines, a stronger major line is drawn"))
        layout.addRow(_("Major line every"), self._major)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(lambda: self._accept())
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _accept(self) -> None:
        self.grid = GridSettings(self._spacing.px(), self._major.value())
        self.accept()
