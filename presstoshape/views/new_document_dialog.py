"""The New Document dialog: presets or custom size, unit, DPI and orientation; at startup also recent files."""

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QLocale, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from presstoshape import icons
from presstoshape.editing.operations.documents import DocumentSetup, setup_problem
from presstoshape.geometry import units
from presstoshape.i18n import _
from presstoshape.models.app_state import Unit
from presstoshape.models.document_presets import DEFAULT, PRESETS, DocumentPreset, find
from presstoshape.views.icon_engine import icon

# `open_path` value when the user asked for the Open dialog.
OPEN = "open"
_PRESET_ROLE = Qt.ItemDataRole.UserRole
_LARGEST_SIDE = 1e9


@dataclass(frozen=True)
class StartChoices:
    """What only the startup dialog shows."""

    recent: list[str]
    show_at_startup: bool
    # Why the last attempt to open a file failed, shown above the recent files.
    error: str | None = None


def _number(value: float, digits: int) -> str:
    """`value` in the interface language's format, without trailing zeros (210, 8,5)."""
    locale = QLocale()
    text = locale.toString(float(round(value, digits)), "f", digits)
    return text.rstrip("0").rstrip(locale.decimalPoint()) if locale.decimalPoint() in text else text


def _size_text(width: float, height: float, unit: Unit) -> str:
    digits = units.DECIMALS[unit]
    return f"{_number(width, digits)} × {_number(height, digits)} {unit}"


def _preset_label(preset: DocumentPreset) -> str:
    return f"{_(preset.name)}  ·  {_size_text(preset.width, preset.height, preset.unit)}"


class NewDocumentDialog(QDialog):
    """Collects a DocumentSetup (or a file to open at startup); creating the document is the caller's job."""

    def __init__(
        self,
        last: tuple[str | None, DocumentSetup] | None = None,
        start: StartChoices | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("New Document"))
        self.preset_id: str | None = None
        self.open_path: str | None = None
        self._filling = False
        self._previous_unit: Unit = DEFAULT.unit

        self._presets = QTreeWidget()
        self._presets.setHeaderHidden(True)
        self._presets.setMinimumWidth(280)
        self._fill_presets()
        self._presets.itemSelectionChanged.connect(self._on_preset_selected)
        self._presets.itemActivated.connect(self._on_preset_activated)

        self._width, self._height = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self._width, self._height):
            spin.setRange(0, _LARGEST_SIDE)
            spin.valueChanged.connect(lambda _value: self._on_edited())
        self._unit = QComboBox()
        for unit in units.UNITS:
            self._unit.addItem(unit, unit)
        self._unit.currentIndexChanged.connect(lambda: self._on_unit_changed())
        self._dpi = QDoubleSpinBox()
        self._dpi.setRange(units.MIN_DPI, units.MAX_DPI)
        self._dpi.setDecimals(1)
        self._dpi.setSuffix(" dpi")
        self._dpi.valueChanged.connect(lambda _value: self._on_edited())
        self._portrait = self._orientation_button(icons.ORIENTATION_PORTRAIT, _("Portrait"), portrait=True)
        self._landscape = self._orientation_button(icons.ORIENTATION_LANDSCAPE, _("Landscape"), portrait=False)
        orientation = QHBoxLayout()
        orientation.addWidget(self._portrait)
        orientation.addWidget(self._landscape)
        orientation.addStretch(1)
        self._hint = QLabel()
        self._hint.setEnabled(False)
        self._problem = QLabel()
        self._problem.setWordWrap(True)

        form = QFormLayout()
        form.addRow(_("Width"), self._width)
        form.addRow(_("Height"), self._height)
        form.addRow(_("Unit"), self._unit)
        form.addRow(_("Resolution"), self._dpi)
        form.addRow(_("Orientation"), orientation)
        form.addRow(self._hint)
        form.addRow(self._problem)
        size_box = QGroupBox(_("Size"))
        size_box.setLayout(form)

        top = QHBoxLayout()
        top.addWidget(self._presets, 1)
        top.addWidget(size_box)
        layout = QVBoxLayout(self)
        layout.addLayout(top, 1)

        self._show_at_startup: QCheckBox | None = None
        if start is not None:
            layout.addWidget(self._start_panel(start))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._create = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._create.setText(_("Create"))
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        if self._show_at_startup is not None:
            bottom = QHBoxLayout()
            bottom.addWidget(self._show_at_startup)
            bottom.addWidget(buttons, 1)
            layout.addLayout(bottom)
        else:
            layout.addWidget(buttons)

        self._preselect(last)
        self._presets.setFocus()
        self.resize(760, 560 if start is not None else 420)

    # --- building ---------------------------------------------------------------------------

    def _fill_presets(self) -> None:
        categories: dict[str, QTreeWidgetItem] = {}
        for preset in PRESETS:
            if preset.category not in categories:
                category = QTreeWidgetItem(self._presets, [_(preset.category)])
                category.setFlags(Qt.ItemFlag.ItemIsEnabled)
                category.setExpanded(True)
                categories[preset.category] = category
            item = QTreeWidgetItem(categories[preset.category], [_preset_label(preset)])
            item.setData(0, _PRESET_ROLE, preset.id)

    def _orientation_button(self, path: Path, tooltip: str, portrait: bool) -> QToolButton:
        button = QToolButton()
        button.setIcon(icon(path))
        button.setIconSize(QSize(22, 22))
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.clicked.connect(lambda: self._set_orientation(portrait))
        return button

    def _start_panel(self, start: StartChoices) -> QWidget:
        box = QGroupBox(_("Recent files"))
        layout = QVBoxLayout(box)
        if start.error:
            error = QLabel(start.error)
            error.setWordWrap(True)
            layout.addWidget(error)
        self._recent = QListWidget()
        self._recent.setMaximumHeight(140)
        for path in start.recent:
            when = time.strftime("%x", time.localtime(Path(path).stat().st_mtime)) if Path(path).exists() else "–"
            item = QListWidgetItem(f"{Path(path).name}    {Path(path).parent}    {when}", self._recent)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
        if not start.recent:
            QListWidgetItem(_("No recent files"), self._recent).setFlags(Qt.ItemFlag.NoItemFlags)
        self._recent.itemActivated.connect(self._on_recent_activated)
        layout.addWidget(self._recent)
        open_button = QPushButton(_("Open…"))
        open_button.clicked.connect(lambda: self._choose_open(OPEN))
        row = QHBoxLayout()
        row.addWidget(open_button)
        row.addStretch(1)
        layout.addLayout(row)
        self._show_at_startup = QCheckBox(_("Show this dialog at startup"))
        self._show_at_startup.setChecked(start.show_at_startup)
        return box

    # --- state ----------------------------------------------------------------------------------

    def _preselect(self, last: tuple[str | None, DocumentSetup] | None) -> None:
        preset_id, setup = last if last is not None else (None, None)
        preset = find(preset_id) if preset_id else None
        if preset is not None and setup is not None and (setup.width, setup.height) != (preset.width, preset.height):
            # A preset turned to landscape: show its values, keep it selected.
            self._select_preset(preset)
            self._show_setup(setup)
        elif preset is not None:
            self._select_preset(preset)
        else:
            fallback = setup or DocumentSetup(DEFAULT.width, DEFAULT.height, DEFAULT.unit, DEFAULT.dpi)
            self._show_setup(fallback)

    def _select_preset(self, preset: DocumentPreset) -> None:
        for category in range(self._presets.topLevelItemCount()):
            parent = self._presets.topLevelItem(category)
            for row in range(parent.childCount()):
                if parent.child(row).data(0, _PRESET_ROLE) == preset.id:
                    self._presets.setCurrentItem(parent.child(row))
                    return

    def _show_setup(self, setup: DocumentSetup) -> None:
        self._filling = True
        self._unit.setCurrentIndex(self._unit.findData(setup.unit))
        self._apply_decimals()
        self._width.setValue(setup.width)
        self._height.setValue(setup.height)
        self._dpi.setValue(setup.dpi)
        self._filling = False
        self._update()

    @property
    def setup(self) -> DocumentSetup:
        return DocumentSetup(self._width.value(), self._height.value(), self._unit.currentData(), self._dpi.value())

    @property
    def show_at_startup(self) -> bool | None:
        return self._show_at_startup.isChecked() if self._show_at_startup is not None else None

    def _apply_decimals(self) -> None:
        for spin in (self._width, self._height):
            spin.setDecimals(units.DECIMALS[self._unit.currentData()])

    # --- reactions -------------------------------------------------------------------------------

    def _on_preset_selected(self) -> None:
        item = self._presets.currentItem()
        preset = find(item.data(0, _PRESET_ROLE)) if item is not None and item.isSelected() else None
        if preset is None:
            return
        self._show_setup(DocumentSetup(preset.width, preset.height, preset.unit, preset.dpi))
        self.preset_id = preset.id

    def _on_preset_activated(self, item: QTreeWidgetItem) -> None:
        if item.data(0, _PRESET_ROLE):
            self._accept_if_valid()

    def _on_edited(self) -> None:
        if not self._filling:
            self._presets.clearSelection()
            self.preset_id = None
        self._update()

    def _on_unit_changed(self) -> None:
        if self._filling:
            return
        previous = self._previous_unit
        unit, dpi = self._unit.currentData(), self._dpi.value()
        self._filling = True
        self._apply_decimals()
        for spin in (self._width, self._height):
            spin.setValue(units.convert(spin.value(), previous, unit, dpi))
        self._filling = False
        self._on_edited()

    def _set_orientation(self, portrait: bool) -> None:
        width, height = self._width.value(), self._height.value()
        if (width > height and portrait) or (width < height and not portrait):
            self._filling = True
            self._width.setValue(height)
            self._height.setValue(width)
            self._filling = False
        self._update()

    def _update(self) -> None:
        setup = self.setup
        self._previous_unit = setup.unit
        self._portrait.setChecked(setup.width <= setup.height)
        self._landscape.setChecked(setup.width >= setup.height)
        problem = setup_problem(setup)
        self._problem.setText(problem or "")
        self._problem.setVisible(problem is not None)
        self._create.setEnabled(problem is None)
        if problem is not None:
            self._hint.clear()
        elif units.is_physical(setup.unit):
            pixels = (units.to_px(side, setup.unit, setup.dpi) for side in (setup.width, setup.height))
            self._hint.setText(" × ".join(str(round(value)) for value in pixels) + " px")
        else:
            millimetres = [units.from_px(side, "mm", setup.dpi) for side in (setup.width, setup.height)]
            self._hint.setText(_size_text(*millimetres, "mm"))

    # --- results ---------------------------------------------------------------------------------

    def _accept_if_valid(self) -> None:
        if setup_problem(self.setup) is None:
            self.open_path = None
            self.accept()

    def _choose_open(self, path: str) -> None:
        self.open_path = path
        self.accept()

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._choose_open(path)
