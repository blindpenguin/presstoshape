from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QWidget

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState
from veccy.views.widgets import ColorButton


class PropertiesPanel(QWidget):
    """Style of the bottom-most selected shape, or the defaults for new shapes when nothing is selected."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._controller = controller
        form = QFormLayout(self)

        self._heading = QLabel()
        form.addRow(self._heading)

        self._fill_check, self._fill_button = QCheckBox(), ColorButton()
        self._stroke_check, self._stroke_button = QCheckBox(), ColorButton()
        form.addRow("Fill", self._row(self._fill_check, self._fill_button))
        form.addRow("Stroke", self._row(self._stroke_check, self._stroke_button))

        self._width = QDoubleSpinBox()
        self._width.setRange(0, 200)
        self._width.setSingleStep(0.5)
        self._width.setDecimals(2)
        form.addRow("Width", self._width)

        self._fill_check.toggled.connect(lambda on: controller.set_fill(self._fill_button.color if on else None))
        self._fill_button.color_picked.connect(controller.set_fill)
        self._stroke_check.toggled.connect(
            lambda on: controller.set_stroke(self._stroke_button.color if on else None)
        )
        self._stroke_button.color_picked.connect(controller.set_stroke)
        self._width.valueChanged.connect(controller.set_stroke_width)

    @staticmethod
    def _row(check: QCheckBox, button: ColorButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(check)
        layout.addWidget(button, 1)
        return row

    def refresh(self, state: AppState) -> None:
        selected = self._controller.selected_shapes()
        style = selected[0].style if selected else state.default_style
        self._heading.setText(f"{len(selected)} selected" if selected else "Defaults for new shapes")

        widgets = (self._fill_check, self._fill_button, self._stroke_check, self._stroke_button, self._width)
        for w in widgets:
            w.blockSignals(True)
        for check, button, color in (
            (self._fill_check, self._fill_button, style.fill),
            (self._stroke_check, self._stroke_button, style.stroke),
        ):
            check.setChecked(color is not None)
            button.setEnabled(color is not None)
            if color is not None:
                button.set_color(color)
        if self._width.value() != style.stroke_width:
            self._width.setValue(style.stroke_width)
        self._width.setEnabled(style.stroke is not None)
        for w in widgets:
            w.blockSignals(False)
