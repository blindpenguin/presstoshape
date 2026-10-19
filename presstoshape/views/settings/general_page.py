from PySide6.QtWidgets import QCheckBox, QVBoxLayout

from presstoshape import icons
from presstoshape.i18n import N_, _
from presstoshape.views import app_settings
from presstoshape.views.settings.pages import SettingsContext, SettingsPage


class GeneralPage(SettingsPage):
    title = N_("General")
    icon = icons.SETTINGS

    def __init__(self, context: SettingsContext) -> None:
        super().__init__(context)
        layout = QVBoxLayout(self)
        self._start_dialog = QCheckBox(_("Show the New Document dialog at startup"))
        self._start_dialog.setChecked(app_settings.show_start_dialog(context.settings))
        self._start_dialog.toggled.connect(lambda on: app_settings.set_show_start_dialog(context.settings, on))
        layout.addWidget(self._start_dialog)
        layout.addStretch(1)
