"""What every settings page gets and provides. A new category is one SettingsPage subclass added to PAGES in
dialog.py."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QWidget

from presstoshape.i18n import _


@dataclass(frozen=True)
class SettingsContext:
    settings: QSettings
    # Language this run uses; a different choice needs a restart.
    running_language: str
    translations_folder: Path


class SettingsPage(QWidget):
    # Untranslated (N_) category name and its icon in the category list.
    title: str
    icon: Path

    def __init__(self, context: SettingsContext) -> None:
        super().__init__()
        self._context = context


def restart_note() -> QLabel:
    """The hint shown next to settings that apply after a restart; pages show/hide it."""
    note = QLabel(_("Takes effect after restarting PressToShape."))
    note.setWordWrap(True)
    note.setEnabled(False)
    return note
