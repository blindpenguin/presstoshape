import shutil
from pathlib import Path

from PySide6.QtCore import QLocale, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from presstoshape import icons
from presstoshape.i18n import N_, _, ngettext
from presstoshape.i18n.languages import (
    ENGLISH,
    TEMPLATE,
    Language,
    available_languages,
    code_for_import,
    locale_name,
    resolve,
)
from presstoshape.i18n.po import PoError, parse_po
from presstoshape.views import app_settings
from presstoshape.views.settings.pages import SettingsContext, SettingsPage, restart_note

# How many reasons an import lists for ignored entries; the rest is summed up.
_SHOWN_PROBLEMS = 10
_FILE_ROLE = Qt.ItemDataRole.UserRole


def language_name(code: str) -> str:
    """The language in its own words ("Deutsch", "Français"), as the system's locale data knows it."""
    locale = QLocale(locale_name(code))
    name = locale.nativeLanguageName()
    if not name or locale.language() == QLocale.Language.C:
        return code
    return name[:1].upper() + name[1:]


class LanguagePage(SettingsPage):
    title = N_("Language")
    icon = icons.SETTINGS_LANGUAGE

    def __init__(self, context: SettingsContext) -> None:
        super().__init__(context)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._choice = QComboBox()
        self._choice.currentIndexChanged.connect(lambda: self._on_choice())
        form.addRow(_("Interface language"), self._choice)
        self._note = restart_note()
        form.addRow(self._note)
        layout.addLayout(form)

        box = QGroupBox(_("Your translations"))
        box_layout = QVBoxLayout(box)
        explanation = QLabel(
            _(
                "Translation files (.po) you add here override or complete the shipped ones, entry by entry. "
                "Start a new language from the template."
            )
        )
        explanation.setWordWrap(True)
        box_layout.addWidget(explanation)
        self._user_files = QListWidget()
        self._user_files.currentRowChanged.connect(lambda: self._update_buttons())
        box_layout.addWidget(self._user_files)
        self._remove_button = QPushButton(_("Remove"))
        buttons = QHBoxLayout()
        for button, slot in (
            (QPushButton(_("Import…")), self._import),
            (self._remove_button, self._remove),
            (QPushButton(_("Open folder")), self._open_folder),
            (QPushButton(_("Save template…")), self._save_template),
        ):
            button.clicked.connect(lambda _checked=False, run=slot: run())
            buttons.addWidget(button)
        buttons.addStretch(1)
        box_layout.addLayout(buttons)
        layout.addWidget(box, 1)
        self._reload()

    # --- state ------------------------------------------------------------------------

    def _languages(self) -> list[Language]:
        return available_languages(self._context.translations_folder)

    def _reload(self) -> None:
        languages = self._languages()
        saved = app_settings.language(self._context.settings)
        self._choice.blockSignals(True)
        self._choice.clear()
        self._choice.addItem(_("System default"), None)
        for language in languages:
            self._choice.addItem(language_name(language.code), language.code)
        index = self._choice.findData(saved) if saved is not None else 0
        self._choice.setCurrentIndex(max(index, 0))
        self._choice.blockSignals(False)

        self._user_files.clear()
        for language in languages:
            if language.user is not None:
                item = QListWidgetItem(f"{language_name(language.code)}  ·  {language.user.name}", self._user_files)
                item.setData(_FILE_ROLE, language.user)
        self._update_note()
        self._update_buttons()

    def _update_note(self) -> None:
        chosen = self._choice.currentData()
        effective = resolve(chosen, QLocale.system().uiLanguages(), self._languages())
        self._note.setVisible(effective != self._context.running_language)

    def _update_buttons(self) -> None:
        self._remove_button.setEnabled(self._user_files.currentItem() is not None)

    def _on_choice(self) -> None:
        app_settings.set_language(self._context.settings, self._choice.currentData())
        self._update_note()

    # --- translation files ------------------------------------------------------------------

    def _import(self) -> None:
        path, _chosen = QFileDialog.getOpenFileName(self, _("Import translation"), "", _("Translation files (*.po)"))
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            po_file = parse_po(text, Path(path).name)
        except (OSError, UnicodeDecodeError, PoError) as error:
            QMessageBox.warning(self, _("Import translation"), _("Can't use this file: {error}").format(error=error))
            return
        code = code_for_import(Path(path).name, po_file.language)
        if code is None or code == ENGLISH:
            QMessageBox.warning(
                self,
                _("Import translation"),
                _("Name the file after its language, for example fr.po or pt_BR.po, and import it again."),
            )
            return
        target = self._context.translations_folder / f"{code}.po"
        if target.exists():
            answer = QMessageBox.question(
                self,
                _("Import translation"),
                _("Replace your existing translation for {language}?").format(language=language_name(code)),
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, _("Import translation"), _("Can't save the file: {error}").format(error=error))
            return
        self._reload()
        message = _("Imported {language}.").format(language=language_name(code))
        if po_file.ignored:
            count = len(po_file.ignored)
            reasons = "\n".join(po_file.ignored[:_SHOWN_PROBLEMS])
            message += "\n\n" + ngettext("{count} entry was ignored:", "{count} entries were ignored:", count).format(
                count=count
            )
            message += "\n" + reasons
        QMessageBox.information(self, _("Import translation"), message)

    def _remove(self) -> None:
        item = self._user_files.currentItem()
        if item is None:
            return
        path: Path = item.data(_FILE_ROLE)
        answer = QMessageBox.question(
            self, _("Remove translation"), _("Remove your translation file {name}?").format(name=path.name)
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as error:
            QMessageBox.warning(self, _("Remove translation"), _("Can't remove the file: {error}").format(error=error))
        self._reload()

    def _open_folder(self) -> None:
        folder = self._context.translations_folder
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.warning(self, _("Open folder"), _("Can't create the folder: {error}").format(error=error))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _save_template(self) -> None:
        path, _chosen = QFileDialog.getSaveFileName(
            self, _("Save translation template"), TEMPLATE.name, _("Translation templates (*.pot)")
        )
        if not path:
            return
        try:
            shutil.copyfile(TEMPLATE, path)
        except OSError as error:
            message = _("Can't save the file: {error}").format(error=error)
            QMessageBox.warning(self, _("Save translation template"), message)
