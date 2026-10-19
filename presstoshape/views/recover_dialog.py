"""Offers the documents of a run that didn't end normally: recover one, discard, or keep them for later."""

from pathlib import Path

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from presstoshape.editing.operations import recovery
from presstoshape.editing.operations.recovery import Snapshot
from presstoshape.formats import p2s
from presstoshape.i18n import _

_PREVIEW_SIZE = QSize(96, 96)
_SNAPSHOT_ROLE = Qt.ItemDataRole.UserRole


def _preview(snapshot: Snapshot) -> QIcon:
    pixmap = QPixmap()
    try:
        data = p2s.read_preview(snapshot.document.read_bytes())
    except OSError:
        data = None
    if data is not None:
        pixmap.loadFromData(data)
    return QIcon(pixmap)


def _description(snapshot: Snapshot) -> str:
    name = snapshot.name or _("Untitled")
    if snapshot.damaged:
        name = _("{name} (damaged, can't be recovered)").format(name=name)
    where = str(Path(snapshot.original_path).parent) if snapshot.original_path else _("Never saved")
    moment = QDateTime.fromSecsSinceEpoch(int(snapshot.saved_at))
    when = _("Last change kept: {time}").format(time=QLocale().toString(moment, QLocale.FormatType.ShortFormat))
    return f"{name}\n{where}\n{when}"


class RecoverDialog(QDialog):
    """`chosen` is the snapshot to recover, or None when the user closed the dialog (the rest stay for later)."""

    def __init__(self, snapshots: list[Snapshot], folder: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Recover Documents"))
        self.chosen: Snapshot | None = None
        self._folder = folder
        explanation = QLabel(
            _(
                "PressToShape didn't close properly last time. These documents had unsaved changes. "
                "Recover one to continue working on it."
            )
        )
        explanation.setWordWrap(True)
        self._list = QListWidget()
        self._list.setIconSize(_PREVIEW_SIZE)
        self._list.setSpacing(4)
        for snapshot in snapshots:
            item = QListWidgetItem(_preview(snapshot), _description(snapshot), self._list)
            item.setData(_SNAPSHOT_ROLE, snapshot)
        self._list.currentItemChanged.connect(lambda: self._update_buttons())
        self._list.itemActivated.connect(lambda: self._recover())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._recover_button = QPushButton(_("Recover"))
        self._recover_button.setDefault(True)
        self._discard_button = QPushButton(_("Discard…"))
        buttons.addButton(self._recover_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self._discard_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        self._recover_button.clicked.connect(lambda: self._recover())
        self._discard_button.clicked.connect(lambda: self._discard())
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(explanation)
        layout.addWidget(self._list, 1)
        layout.addWidget(buttons)
        self._list.setCurrentRow(0)
        self.resize(560, 420)

    def _selected(self) -> Snapshot | None:
        item = self._list.currentItem()
        return item.data(_SNAPSHOT_ROLE) if item is not None else None

    def _update_buttons(self) -> None:
        snapshot = self._selected()
        self._recover_button.setEnabled(snapshot is not None and not snapshot.damaged)
        self._discard_button.setEnabled(snapshot is not None)

    def _recover(self) -> None:
        snapshot = self._selected()
        if snapshot is not None and not snapshot.damaged:
            self.chosen = snapshot
            self.accept()

    def _discard(self) -> None:
        snapshot = self._selected()
        if snapshot is None:
            return
        answer = QMessageBox.question(
            self,
            _("Discard recovered document"),
            _("Discard the unsaved changes of {name} for good?").format(name=snapshot.name or _("Untitled")),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            recovery.discard_snapshot(self._folder, snapshot.run_id)
        except OSError as error:
            QMessageBox.warning(self, _("Discard recovered document"), str(error))
            return
        self._list.takeItem(self._list.currentRow())
        if self._list.count() == 0:
            self.reject()
        self._update_buttons()
