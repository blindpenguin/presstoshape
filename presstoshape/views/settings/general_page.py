from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QVBoxLayout

from presstoshape import icons
from presstoshape.i18n import N_, _, ngettext
from presstoshape.views import app_settings
from presstoshape.views.settings.pages import SettingsContext, SettingsPage


def _interval_label(minutes: int) -> str:
    if minutes == 0:
        return _("Off")
    return ngettext("{count} minute", "{count} minutes", minutes).format(count=minutes)


class GeneralPage(SettingsPage):
    title = N_("General")
    icon = icons.SETTINGS

    def __init__(self, context: SettingsContext) -> None:
        super().__init__(context)
        settings = context.settings
        layout = QVBoxLayout(self)
        self._start_dialog = QCheckBox(_("Show the New Document dialog at startup"))
        self._start_dialog.setChecked(app_settings.show_start_dialog(settings))
        self._start_dialog.toggled.connect(lambda on: app_settings.set_show_start_dialog(settings, on))
        layout.addWidget(self._start_dialog)

        form = QFormLayout()
        self._recovery = QComboBox()
        for minutes in app_settings.RECOVERY_INTERVALS:
            self._recovery.addItem(_interval_label(minutes), minutes)
        self._recovery.setCurrentIndex(self._recovery.findData(app_settings.recovery_interval(settings)))
        self._recovery.currentIndexChanged.connect(
            lambda: app_settings.set_recovery_interval(settings, self._recovery.currentData())
        )
        form.addRow(_("Save recovery data every"), self._recovery)
        layout.addLayout(form)
        self._backups = QCheckBox(_("Keep a backup of the previous version when saving"))
        self._backups.setChecked(app_settings.keep_backups(settings))
        self._backups.toggled.connect(lambda on: app_settings.set_keep_backups(settings, on))
        layout.addWidget(self._backups)
        layout.addStretch(1)
