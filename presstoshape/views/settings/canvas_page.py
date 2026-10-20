from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QSpinBox

from presstoshape import icons
from presstoshape.i18n import N_, _
from presstoshape.views import app_settings
from presstoshape.views.settings.pages import SettingsContext, SettingsPage, restart_note
from presstoshape.views.skia_surface import RENDERER_VARIABLE, renderer_override


class CanvasPage(SettingsPage):
    title = N_("Canvas")
    icon = icons.SETTINGS_CANVAS

    def __init__(self, context: SettingsContext) -> None:
        super().__init__(context)
        self._initial = app_settings.renderer(context.settings)
        form = QFormLayout(self)
        self._renderer = QComboBox()
        for value, label in (("auto", _("Automatic")), ("gl", _("GPU (OpenGL)")), ("cpu", _("CPU"))):
            self._renderer.addItem(label, value)
        self._renderer.setCurrentIndex(self._renderer.findData(self._initial))
        self._renderer.currentIndexChanged.connect(lambda: self._on_renderer())
        form.addRow(_("Renderer"), self._renderer)
        self._snap_distance = QSpinBox()
        self._snap_distance.setRange(2, 30)
        self._snap_distance.setSuffix(" px")
        self._snap_distance.setValue(round(app_settings.snap_settings(context.settings).distance_px))
        self._snap_distance.setToolTip(_("How close (on screen) a dragged object must come to a target to snap"))
        self._snap_distance.valueChanged.connect(lambda value: self._on_snap_distance(value))
        form.addRow(_("Snap distance"), self._snap_distance)
        self._note = restart_note()
        self._note.setVisible(False)
        form.addRow(self._note)
        forced = renderer_override()
        if forced is not None:
            hint = QLabel(
                _("The {variable} environment variable currently forces {renderer}.").format(
                    variable=RENDERER_VARIABLE, renderer=self._renderer.itemText(self._renderer.findData(forced))
                )
            )
            hint.setWordWrap(True)
            form.addRow(hint)

    def _on_snap_distance(self, value: int) -> None:
        settings = self._context.settings
        app_settings.set_snap_settings(settings, replace(app_settings.snap_settings(settings), distance_px=float(value)))

    def _on_renderer(self) -> None:
        value = self._renderer.currentData()
        app_settings.set_renderer(self._context.settings, value)
        self._note.setVisible(value != self._initial)
